using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection.Metadata;
using System.Runtime.InteropServices;

namespace PlumbSpec.Instrumenter
{
    /// <summary>
    /// The weave, carried out as the runtime compiles: the same probes the static weave wrote into a
    /// copy, written now into each method's instruction graph, in the build's own output.
    /// </summary>
    /// <remarks>
    /// <para>What to weave is declared by the adapter (<c>PLUMB_PLAN</c>): the tests assembly, the
    /// production assemblies, the entry points and the hand-off shims — and no token (dev07-1-3-sr03).
    /// Each module's tokens are read from the module as the runtime loads it, by the same
    /// <see cref="Planning"/> the adapter uses: another tool may rewrite the file on disk before the
    /// testhost starts — measured, Microsoft's coverage does — and a token read before then names
    /// something else. The probe's own tokens are minted through the runtime's metadata emitter and
    /// the graph is edited through the engine, so this composes with any other instrumenter.</para>
    /// <para>Interface pointers the engine hands out are not released — the prototype leaks one per
    /// call into it.</para>
    /// </remarks>
    internal static unsafe class Weave
    {
        private static readonly Guid IMetaDataEmit = new("BA3FEE4C-ECB9-4E41-83B7-183FA41CD859");
        private static readonly Guid IMetaDataEmit2 = new("F5DD9950-F693-42E6-830E-7B833E8146A9");
        private static readonly Guid IMetaDataAssemblyEmit = new("211EF15B-5317-4438-B196-DEC87B887693");
        private static readonly Guid IOperandInstruction = new("1F014299-F383-46CE-B7A6-1982C85F9FEA");

        private const int Call = 0x28, Callvirt = 0x6F, Newobj = 0x73, Ret = 0x2A, Jmp = 0x27,
                          Leave = 0xDD, Endfinally = 0xDC, Stloc = 0x10E, Ldloc = 0x10C,
                          Tailcall = 0x114, Ldstr = 0x72, Ldnull = 0x14, Ldarg0 = 0x02;

        private sealed class ModulePlan
        {
            public bool Production;
            public readonly Dictionary<int, string> Entries = new();
            public readonly HashSet<int> Steps = new();
            public readonly Dictionary<int, (bool Static, string Type, string Method)> Tests = new();
            public readonly List<(int Call, string Shim, byte[] Signature, byte[]? Instantiation)> Handoffs = new();
            public readonly HashSet<int> Calls = new();
            public readonly object Gate = new();
            public Tokens? Minted;
        }

        private sealed class Tokens
        {
            public int Ran, Enter, Exit, Resume, Suspend, Begin;
            public readonly Dictionary<int, int> Retarget = new();
        }

        /// <summary>What the adapter declared: read once, before the first module is asked about.</summary>
        private sealed class Declared
        {
            public string Tests = "";
            public readonly List<string> Production = new();
            public readonly HashSet<string> EntryPoints = new(StringComparer.Ordinal);
            public readonly Dictionary<string, (string Shim, Call Call)> Shims = new(StringComparer.Ordinal);
        }

        private static readonly Declared Declaration = Read();
        private static readonly HashSet<string> Found = new(StringComparer.Ordinal);
        private static readonly ConcurrentDictionary<ulong, ModulePlan?> ByModule = new();

        private static Declared Read()
        {
            var declared = new Declared();
            var path = Environment.GetEnvironmentVariable("PLUMB_PLAN");
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return declared;
            foreach (var line in File.ReadAllLines(path))
            {
                var f = line.Split('\t');
                switch (f[0])
                {
                    case "tests": declared.Tests = f[1]; break;
                    case "production": declared.Production.Add(f[1]); break;
                    case "entrypoint": declared.EntryPoints.Add(f[1]); break;
                    case "shim": declared.Shims[f[1]] = (f[2], Enum.Parse<Call>(f[3])); break;
                }
            }
            return declared;
        }

        /// <summary>
        /// The module's plan, read from the module as it was loaded: the file at its path now holds
        /// what the runtime loaded, whatever rewrote it first. Nothing for a module that is neither
        /// the tests nor production.
        /// </summary>
        private static ModulePlan? PlanFor(string path)
        {
            try
            {
                using var pe = new System.Reflection.PortableExecutable.PEReader(
                    File.OpenRead(path), System.Reflection.PortableExecutable.PEStreamOptions.PrefetchEntireImage);
                if (!pe.HasMetadata) return null;
                var md = pe.GetMetadataReader();
                if (!md.IsAssembly) return null;
                var isTests = string.Equals(Path.GetFileName(path), Declaration.Tests, StringComparison.Ordinal);
                var name = md.GetString(md.GetAssemblyDefinition().Name);
                if (!isTests && !Declaration.Production.Any(p => Planning.Matches(name, p))) return null;
                Planning.ModulePlan read;
                lock (Found) read = Planning.ForModule(pe, isTests, Declaration.EntryPoints, Found, Declaration.Shims);
                var plan = new ModulePlan { Production = !isTests };
                foreach (var (token, entry) in read.Entries) plan.Entries[token] = entry;
                plan.Steps.UnionWith(read.Steps);
                foreach (var (token, test) in read.Tests) plan.Tests[token] = test;
                plan.Calls.UnionWith(read.Calls);
                foreach (var site in read.Handoffs)
                    plan.Handoffs.Add((site.Call, site.Shim, site.ShimSignature,
                                       site.Instantiation is { } spec ? md.GetBlobBytes(spec) : null));
                return plan;
            }
            catch (Exception failed) when (failed is IOException or BadImageFormatException or UnauthorizedAccessException)
            {
                Log.Say($"unread {path}: {failed.Message}");
                return null;
            }
        }

        public static bool Wanted(void* method)
        {
            var (plan, token, _) = Find(method);
            if (plan == null) return false;
            return plan.Production || plan.Tests.ContainsKey(token) || plan.Steps.Contains(token) ||
                   plan.Calls.Contains(token);
        }

        public static void Instrument(void* method)
        {
            var (plan, token, module) = Find(method);
            if (plan == null) return;
            var tokens = Mint(plan, module);
            void* graph, factory;
            Check(Out(method, 6, &graph), "IMethodInfo.GetInstructions");
            Check(Out(method, 32, &factory), "IMethodInfo.GetInstructionFactory");

            Retarget(graph, factory, tokens.Retarget);
            if (plan.Production)
            {
                if (plan.Entries.TryGetValue(token, out var entry))
                    Wrap(method, graph, factory,
                         new[] { Token(factory, Ldstr, UserString(module, entry)), Token(factory, Call, tokens.Enter) },
                         tokens.Exit);
                else if (plan.Steps.Contains(token))
                    Wrap(method, graph, factory,
                         new[] { Token(factory, Call, tokens.Ran), Token(factory, Call, tokens.Resume) }, tokens.Suspend);
                else
                    Prefix(graph, new[] { Token(factory, Call, tokens.Ran) });
            }
            else if (plan.Steps.Contains(token))
                Wrap(method, graph, factory, new[] { Token(factory, Call, tokens.Resume) }, tokens.Suspend);
            else if (plan.Tests.TryGetValue(token, out var test))
                Prefix(graph, new[]
                {
                    // The instance, so a test inherited from a base class is named for the class it
                    // ran in, as VSTest names it; nothing for a static test.
                    Plain(factory, test.Static ? Ldnull : Ldarg0),
                    Token(factory, Ldstr, UserString(module, test.Type)),
                    Token(factory, Ldstr, UserString(module, test.Method)),
                    Token(factory, Call, tokens.Begin),
                });
        }

        private static (ModulePlan? Plan, int Token, IntPtr Module) Find(void* method)
        {
            void* module;
            Check(Out(method, 3, &module), "IMethodInfo.GetModuleInfo");
            ulong id;
            Check(Out(module, 11, &id), "IModuleInfo.GetModuleID");
            if (!ByModule.TryGetValue(id, out var plan))
            {
                char* path;
                Check(Out(module, 4, &path), "IModuleInfo.GetFullPath");
                ByModule[id] = plan = path == null ? null : PlanFor(new string(path));
            }
            int token = 0;
            if (plan != null) Check(Out(method, 10, &token), "IMethodInfo.GetMethodToken");
            return (plan, token, (IntPtr)module);
        }

        /// <summary>The prologue before the method's first instruction; nothing else moves.</summary>
        private static void Prefix(void* graph, IntPtr[] prologue)
        {
            void* first;
            Check(Out(graph, 4, &first), "IInstructionGraph.GetFirstInstruction");
            foreach (var p in prologue) Insert(graph, 13, first, (void*)p, "InsertBefore");
        }

        /// <summary>
        /// <c>prologue; try { body } finally { call exit }</c>, every <c>ret</c> made a <c>leave</c> to
        /// one shared return holding the result in a local the engine adds — the only way out of a
        /// protected region, and what closes the window on a throw as on a return.
        /// </summary>
        private static void Wrap(void* method, void* graph, void* factory, IntPtr[] prologue, int exit)
        {
            var instructions = Walk(graph);
            if (instructions.Any(i => OpCode(i) == Jmp))
                throw new InvalidOperationException("it uses `jmp`, which cannot leave a protected region");
            void* type;
            Check(Out(method, 22, &type), "IMethodInfo.GetReturnType");
            int element;
            Check(Out(type, 4, &element), "IType.GetCorElementType");
            if (element == 0x10) throw new InvalidOperationException("it returns by reference");
            var returns = element != 0x01;
            uint local = 0;
            if (returns)
            {
                void* locals;
                Check(Out(method, 7, &locals), "IMethodInfo.GetLocalVariables");
                Check(((delegate* unmanaged<void*, void*, uint*, int>)Com.Slot(locals, 6))(locals, type, &local),
                      "ILocalVariableCollection.AddLocal");
            }

            void* last;
            Check(Out(graph, 5, &last), "IInstructionGraph.GetLastInstruction");
            var leaveFor = Token(factory, Call, exit);
            var endFinally = Plain(factory, Endfinally);
            var end = returns ? UShort(factory, Ldloc, (ushort)local) : Plain(factory, Ret);
            Insert(graph, 14, last, (void*)leaveFor, "InsertAfter");
            Insert(graph, 14, (void*)leaveFor, (void*)endFinally, "InsertAfter");
            Insert(graph, 14, (void*)endFinally, (void*)end, "InsertAfter");
            if (returns) Insert(graph, 14, (void*)end, (void*)Plain(factory, Ret), "InsertAfter");

            foreach (var instruction in instructions)
            {
                var op = OpCode(instruction);
                if (op == Ret)
                {
                    var leave = Branch(factory, Leave, end);
                    Check(((delegate* unmanaged<void*, void*, void*, int>)Com.Slot(graph, 16))(
                        graph, (void*)instruction, (void*)leave), "IInstructionGraph.Replace");
                    if (returns)
                        Insert(graph, 15, (void*)leave, (void*)UShort(factory, Stloc, (ushort)local),
                               "InsertBeforeAndRetargetOffsets");
                }
                // `tail.` before a call followed by `ret`: a tail call cannot leave a protected region.
                else if (op == Tailcall)
                    Check(((delegate* unmanaged<void*, void*, int>)Com.Slot(graph, 17))(graph, (void*)instruction),
                          "IInstructionGraph.Remove");
            }

            void* tryFirst, tryLast;
            Check(Out(graph, 4, &tryFirst), "IInstructionGraph.GetFirstInstruction");
            Check(Out((void*)leaveFor, 21, &tryLast), "IInstruction.GetPreviousInstruction");
            foreach (var p in prologue) Insert(graph, 13, tryFirst, (void*)p, "InsertBefore");
            void* section, clause;
            Check(Out(method, 31, &section), "IMethodInfo.GetExceptionSection");
            Check(((delegate* unmanaged<void*, uint, void*, void*, void*, void*, void*, int, void**, int>)
                Com.Slot(section, 8))(section, 0x2, tryFirst, tryLast, (void*)leaveFor, (void*)endFinally,
                                      null, 0, &clause), "IExceptionSection.AddNewExceptionClause");
        }

        /// <summary>Each call to a hand-off primitive made a call to the shim that stands in for it
        /// (dev07-1-4-sr2): the stack is the same either way.</summary>
        private static void Retarget(void* graph, void* factory, Dictionary<int, int> retarget)
        {
            if (retarget.Count == 0) return;
            foreach (var instruction in Walk(graph))
            {
                var op = OpCode(instruction);
                if (op != Call && op != Callvirt && op != Newobj) continue;
                void* operand;
                if (Query((void*)instruction, IOperandInstruction, &operand) < 0) continue;
                int token;
                Check(((delegate* unmanaged<void*, uint, byte*, int>)Com.Slot(operand, 4))(operand, 4, (byte*)&token),
                      "IOperandInstruction.GetOperandValue");
                if (!retarget.TryGetValue(token, out var shim)) continue;
                Check(((delegate* unmanaged<void*, void*, void*, int>)Com.Slot(graph, 16))(
                    graph, (void*)instruction, (void*)Token(factory, Call, shim)), "IInstructionGraph.Replace");
            }
        }

        /// <summary>The probe's members, and every shim the plan names, as tokens in this module —
        /// minted once, through the runtime's own metadata emitter.</summary>
        private static Tokens Mint(ModulePlan plan, IntPtr moduleHandle)
        {
            lock (plan.Gate)
            {
                if (plan.Minted != null) return plan.Minted;
                var module = (void*)moduleHandle;
                var emit = Emitter(module, IMetaDataEmit);
                void* assemblyUnknown, assemblyEmit;
                Check(Out(module, 10, &assemblyUnknown), "IModuleInfo.GetMetaDataAssemblyEmit");
                Check(Query(assemblyUnknown, IMetaDataAssemblyEmit, &assemblyEmit), "QueryInterface(IMetaDataAssemblyEmit)");
                var version = new AssemblyMetadata { Major = 1 };
                int assemblyRef;
                fixed (char* assembly = "PlumbSpec.Adapter")
                    Check(((delegate* unmanaged<void*, void*, uint, char*, AssemblyMetadata*, void*, uint, uint, int*, int>)
                        Com.Slot(assemblyEmit, 4))(assemblyEmit, null, 0, assembly, &version, null, 0, 0, &assemblyRef),
                        "IMetaDataAssemblyEmit.DefineAssemblyRef");
                var probe = TypeRef(emit, assemblyRef, "PlumbSpec.Probe");
                var tokens = new Tokens
                {
                    Ran = MemberRef(emit, probe, "Ran", new byte[] { 0x00, 0x00, 0x01 }),
                    Enter = MemberRef(emit, probe, "Enter", new byte[] { 0x00, 0x01, 0x01, 0x0E }),
                    Exit = MemberRef(emit, probe, "Exit", new byte[] { 0x00, 0x00, 0x01 }),
                    Resume = MemberRef(emit, probe, "Resume", new byte[] { 0x00, 0x00, 0x01 }),
                    Suspend = MemberRef(emit, probe, "Suspend", new byte[] { 0x00, 0x00, 0x01 }),
                    Begin = MemberRef(emit, probe, "Begin", new byte[] { 0x00, 0x03, 0x01, 0x1C, 0x0E, 0x0E }),
                };
                if (plan.Handoffs.Count > 0)
                {
                    var handoff = TypeRef(emit, assemblyRef, "PlumbSpec.Handoff");
                    var emit2 = Emitter(module, IMetaDataEmit2);
                    var shims = new Dictionary<string, int>(StringComparer.Ordinal);
                    foreach (var (call, shim, signature, instantiation) in plan.Handoffs)
                    {
                        var key = shim + Convert.ToHexString(signature);
                        if (!shims.TryGetValue(key, out var reference))
                            shims[key] = reference = MemberRef(emit, handoff, shim, signature);
                        tokens.Retarget[call] = instantiation == null ? reference : MethodSpec(emit2, reference, instantiation);
                    }
                }
                return plan.Minted = tokens;
            }
        }

        private static void* Emitter(void* module, Guid iid)
        {
            void* unknown, emit;
            Check(Out(module, 9, &unknown), "IModuleInfo.GetMetaDataEmit");
            Check(Query(unknown, iid, &emit), "QueryInterface(IMetaDataEmit)");
            return emit;
        }

        private static int TypeRef(void* emit, int scope, string name)
        {
            int token;
            fixed (char* type = name)
                Check(((delegate* unmanaged<void*, int, char*, int*, int>)Com.Slot(emit, 12))(emit, scope, type, &token),
                      "IMetaDataEmit.DefineTypeRefByName");
            return token;
        }

        private static int MemberRef(void* emit, int typeRef, string name, byte[] signature)
        {
            int token;
            fixed (char* member = name)
            fixed (byte* sig = signature)
                Check(((delegate* unmanaged<void*, int, char*, byte*, uint, int*, int>)Com.Slot(emit, 14))(
                    emit, typeRef, member, sig, (uint)signature.Length, &token), "IMetaDataEmit.DefineMemberRef");
            return token;
        }

        private static int MethodSpec(void* emit2, int method, byte[] instantiation)
        {
            int token;
            fixed (byte* sig = instantiation)
                Check(((delegate* unmanaged<void*, int, byte*, uint, int*, int>)Com.Slot(emit2, 52))(
                    emit2, method, sig, (uint)instantiation.Length, &token), "IMetaDataEmit2.DefineMethodSpec");
            return token;
        }

        private static int UserString(IntPtr module, string value)
        {
            var emit = Emitter((void*)module, IMetaDataEmit);
            int token;
            fixed (char* text = value)
                Check(((delegate* unmanaged<void*, char*, uint, int*, int>)Com.Slot(emit, 28))(
                    emit, text, (uint)value.Length, &token), "IMetaDataEmit.DefineUserString");
            return token;
        }

        private static List<IntPtr> Walk(void* graph)
        {
            var all = new List<IntPtr>();
            void* at;
            Check(Out(graph, 4, &at), "IInstructionGraph.GetFirstInstruction");
            while (at != null)
            {
                all.Add((IntPtr)at);
                void* next = null;
                if (Out(at, 20, &next) != Com.S_OK) break;
                at = next;
            }
            return all;
        }

        private static int OpCode(IntPtr instruction)
        {
            int op;
            Check(Out((void*)instruction, 6, &op), "IInstruction.GetOpCode");
            return op;
        }

        private static void Insert(void* graph, int slot, void* at, void* instruction, string what) =>
            Check(((delegate* unmanaged<void*, void*, void*, int>)Com.Slot(graph, slot))(graph, at, instruction),
                  "IInstructionGraph." + what);

        private static IntPtr Token(void* factory, int opcode, int token)
        {
            void* instruction;
            Check(((delegate* unmanaged<void*, int, int, void**, int>)Com.Slot(factory, 10))(
                factory, opcode, token, &instruction), "IInstructionFactory.CreateTokenOperandInstruction");
            return (IntPtr)instruction;
        }

        private static IntPtr Plain(void* factory, int opcode)
        {
            void* instruction;
            Check(((delegate* unmanaged<void*, int, void**, int>)Com.Slot(factory, 3))(factory, opcode, &instruction),
                  "IInstructionFactory.CreateInstruction");
            return (IntPtr)instruction;
        }

        private static IntPtr UShort(void* factory, int opcode, ushort operand)
        {
            void* instruction;
            Check(((delegate* unmanaged<void*, int, ushort, void**, int>)Com.Slot(factory, 5))(
                factory, opcode, operand, &instruction), "IInstructionFactory.CreateUShortOperandInstruction");
            return (IntPtr)instruction;
        }

        private static IntPtr Branch(void* factory, int opcode, IntPtr target)
        {
            void* instruction;
            Check(((delegate* unmanaged<void*, int, void*, void**, int>)Com.Slot(factory, 11))(
                factory, opcode, (void*)target, &instruction), "IInstructionFactory.CreateBranchInstruction");
            return (IntPtr)instruction;
        }

        public static string FullName(void* method)
        {
            char* name;
            Check(((delegate* unmanaged<void*, char**, int>)Com.Slot(method, 5))(method, &name),
                  "IMethodInfo.GetFullName");
            return name == null ? "" : new string(name);
        }

        private static int Out(void* self, int slot, void* result) =>
            ((delegate* unmanaged<void*, void*, int>)Com.Slot(self, slot))(self, result);

        private static int Query(void* self, Guid iid, void** result) =>
            ((delegate* unmanaged<void*, Guid*, void**, int>)Com.Slot(self, 0))(self, &iid, result);

        private static void Check(int hr, string what)
        {
            if (hr < 0) throw new InvalidOperationException($"{what} failed: 0x{hr:x8}");
        }

        /// <summary>ASSEMBLYMETADATA (cor.h), laid out as the runtime reads it on a 64-bit platform.</summary>
        [StructLayout(LayoutKind.Sequential)]
        private struct AssemblyMetadata
        {
            public ushort Major, Minor, Build, Revision;
            public char* Locale;
            public uint LocaleLength;
            public uint* Processors;
            public uint ProcessorCount;
            public void* OperatingSystems;
            public uint OperatingSystemCount;
        }
    }
}
