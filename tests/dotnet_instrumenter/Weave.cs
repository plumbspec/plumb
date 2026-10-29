using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;

namespace PlumbSpec.Instrumenter
{
    /// <summary>
    /// The weave, at JIT time: a <c>call PlumbSpec.Probe::Ran()</c> at the top of a production
    /// method, and <c>Probe.Begin(this, type, name)</c> at the top of a test — the same calls the static
    /// weave wrote into a copy, written now into the method as the runtime compiles it.
    /// </summary>
    /// <remarks>
    /// What is production and what is a test arrives by name for the prototype
    /// (<c>PLUMB_PROTO_PRODUCTION</c>, <c>PLUMB_PROTO_TESTS</c>); recognising them as the static weave
    /// does is what moves here once the mechanism is proven. Interface pointers the engine hands out
    /// are not released — the prototype leaks one per woven method.
    /// </remarks>
    internal static unsafe class Weave
    {
        private static readonly Guid IMetaDataEmit = new("BA3FEE4C-ECB9-4E41-83B7-183FA41CD859");
        private static readonly Guid IMetaDataAssemblyEmit = new("211EF15B-5317-4438-B196-DEC87B887693");

        private static readonly HashSet<string> Production = Names("PLUMB_PROTO_PRODUCTION");
        private static readonly HashSet<string> Tests = Names("PLUMB_PROTO_TESTS");

        /// <summary>The probe's members as tokens in each module, minted once per module.</summary>
        private static readonly ConcurrentDictionary<ulong, (int Ran, int Begin)> Tokens = new();

        private static HashSet<string> Names(string variable) =>
            new((Environment.GetEnvironmentVariable(variable) ?? "")
                .Split(';', StringSplitOptions.RemoveEmptyEntries), StringComparer.Ordinal);

        public static bool Wanted(void* method)
        {
            var name = FullName(method);
            if (name.StartsWith("Sample.", StringComparison.Ordinal)) Log.Say($"method {name}");
            return Production.Contains(name) || Tests.Contains(name);
        }

        public static void Instrument(void* method)
        {
            var name = FullName(method);
            void* module;
            Check(Out(method, 3, &module), "IMethodInfo.GetModuleInfo");
            ulong moduleId;
            Check(Out(module, 11, &moduleId), "IModuleInfo.GetModuleID");
            if (!Tokens.TryGetValue(moduleId, out var tokens)) Tokens[moduleId] = tokens = Mint(module);

            void* graph, factory, first;
            Check(Out(method, 6, &graph), "IMethodInfo.GetInstructions");
            Check(Out(method, 32, &factory), "IMethodInfo.GetInstructionFactory");
            Check(Out(graph, 4, &first), "IInstructionGraph.GetFirstInstruction");

            var prologue = new List<IntPtr>();
            if (Production.Contains(name))
            {
                prologue.Add(Token(factory, 0x28, tokens.Ran));                     // call Probe.Ran
            }
            else
            {
                int isStatic;
                Check(Out(method, 12, &isStatic), "IMethodInfo.GetIsStatic");
                var dot = name.LastIndexOf('.');
                prologue.Add(Plain(factory, isStatic != 0 ? 0x14 : 0x02));          // ldnull | ldarg.0
                prologue.Add(Token(factory, 0x72, UserString(module, name[..dot])));  // ldstr type
                prologue.Add(Token(factory, 0x72, UserString(module, name[(dot + 1)..])));
                prologue.Add(Token(factory, 0x28, tokens.Begin));                   // call Probe.Begin
            }
            foreach (var instruction in prologue)
                Check(((delegate* unmanaged<void*, void*, void*, int>)Com.Slot(graph, 13))(
                    graph, first, (void*)instruction), "IInstructionGraph.InsertBefore");
            Log.Say($"woven {name}");
        }

        /// <summary>A reference to plumb's assembly, its probe type and the two members, defined in
        /// the module being instrumented — through the runtime's own metadata emitter.</summary>
        private static (int Ran, int Begin) Mint(void* module)
        {
            void* unknown, assemblyUnknown, emit, assemblyEmit;
            Check(Out(module, 9, &unknown), "IModuleInfo.GetMetaDataEmit");
            Check(Out(module, 10, &assemblyUnknown), "IModuleInfo.GetMetaDataAssemblyEmit");
            Check(Query(unknown, IMetaDataEmit, &emit), "QueryInterface(IMetaDataEmit)");
            Check(Query(assemblyUnknown, IMetaDataAssemblyEmit, &assemblyEmit), "QueryInterface(IMetaDataAssemblyEmit)");

            var version = new AssemblyMetadata { Major = 1 };
            int assemblyRef, typeRef, ran, begin;
            fixed (char* assembly = "PlumbSpec.Adapter")
                Check(((delegate* unmanaged<void*, void*, uint, char*, AssemblyMetadata*, void*, uint, uint, int*, int>)
                    Com.Slot(assemblyEmit, 4))(assemblyEmit, null, 0, assembly, &version, null, 0, 0, &assemblyRef),
                    "IMetaDataAssemblyEmit.DefineAssemblyRef");
            fixed (char* type = "PlumbSpec.Probe")
                Check(((delegate* unmanaged<void*, int, char*, int*, int>)Com.Slot(emit, 12))(
                    emit, assemblyRef, type, &typeRef), "IMetaDataEmit.DefineTypeRefByName");
            ran = MemberRef(emit, typeRef, "Ran", new byte[] { 0x00, 0x00, 0x01 });
            begin = MemberRef(emit, typeRef, "Begin", new byte[] { 0x00, 0x03, 0x01, 0x1C, 0x0E, 0x0E });
            return (ran, begin);
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

        private static int UserString(void* module, string value)
        {
            void* unknown, emit;
            Check(Out(module, 9, &unknown), "IModuleInfo.GetMetaDataEmit");
            Check(Query(unknown, IMetaDataEmit, &emit), "QueryInterface(IMetaDataEmit)");
            int token;
            fixed (char* text = value)
                Check(((delegate* unmanaged<void*, char*, uint, int*, int>)Com.Slot(emit, 28))(
                    emit, text, (uint)value.Length, &token), "IMetaDataEmit.DefineUserString");
            return token;
        }

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
            Check(((delegate* unmanaged<void*, int, void**, int>)Com.Slot(factory, 3))(
                factory, opcode, &instruction), "IInstructionFactory.CreateInstruction");
            return (IntPtr)instruction;
        }

        private static string FullName(void* method)
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
