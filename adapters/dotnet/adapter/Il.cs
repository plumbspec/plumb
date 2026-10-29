using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection.Metadata;

namespace PlumbSpec
{
    /// <summary>
    /// Method bodies: read one, give it a prologue or a wrap, and write it back as a fat body.
    /// </summary>
    /// <remarks>
    /// A prologue moves every instruction by the same distance, and a branch is relative, so only the
    /// handlers move with it. A wrap is not uniform — each <c>ret</c> becomes a <c>leave</c> — so the
    /// body is decoded, every branch is written long, and every target is mapped through the new
    /// layout. Nothing here knows what the probe does; it is handed the tokens to call.
    /// </remarks>
    internal static class Il
    {
        /// <summary>A body no instruction of which this writer will move, named so the caller can
        /// leave the method exactly as it was (dev07-1-3-nfr3).</summary>
        internal sealed class Unweavable : Exception
        {
            public Unweavable(string why) : base(why) { }
        }

        internal sealed record Region(ExceptionRegionKind Kind, int TryOffset, int TryLength,
                                      int HandlerOffset, int HandlerLength, int ClassTokenOrFilter);

        internal sealed record Body(byte[] Code, int MaxStack, int LocalSignatureToken,
                                    bool InitLocals, List<Region> Regions);

        public static Body Read(MethodBodyBlock block)
        {
            var regions = new List<Region>();
            foreach (var r in block.ExceptionRegions)
                regions.Add(new Region(r.Kind, r.TryOffset, r.TryLength, r.HandlerOffset,
                    r.HandlerLength,
                    r.Kind == ExceptionRegionKind.Filter ? r.FilterOffset
                    : r.CatchType.IsNil ? 0 : System.Reflection.Metadata.Ecma335.MetadataTokens.GetToken(r.CatchType)));
            return new Body(block.GetILBytes() ?? Array.Empty<byte>(), block.MaxStack,
                block.LocalSignature.IsNil ? 0
                    : System.Reflection.Metadata.Ecma335.MetadataTokens.GetToken(block.LocalSignature),
                block.LocalVariablesInitialized, regions);
        }

        /// <summary>The body with <paramref name="prologue"/> in front of it, and nothing else
        /// moved but the handlers.</summary>
        public static Body Prefix(Body body, byte[] prologue, int stackNeeded)
        {
            var code = new byte[prologue.Length + body.Code.Length];
            prologue.CopyTo(code, 0);
            body.Code.CopyTo(code, prologue.Length);
            var moved = body.Regions.ConvertAll(r => r with
            {
                TryOffset = r.TryOffset + prologue.Length,
                HandlerOffset = r.HandlerOffset + prologue.Length,
                ClassTokenOrFilter = r.Kind == ExceptionRegionKind.Filter
                    ? r.ClassTokenOrFilter + prologue.Length : r.ClassTokenOrFilter,
            });
            return body with { Code = code, MaxStack = Math.Max(body.MaxStack, stackNeeded), Regions = moved };
        }

        /// <summary>
        /// The body inside <c>try { … } finally { exit }</c>, entered by <paramref name="enter"/>.
        /// Every <c>ret</c> becomes a <c>leave</c> to one shared return after the handler, holding
        /// the result in local <paramref name="resultLocal"/> when there is one — the only way out
        /// of a protected region, and the reason the window closes on a throw as on a return.
        /// </summary>
        public static Body Wrap(Body body, byte[] enter, byte[] exit, int? resultLocal,
                                int localSignatureToken)
        {
            var instructions = Decode(body.Code);
            var start = new Dictionary<int, int>();
            var at = enter.Length;
            foreach (var i in instructions)
            {
                start[i.Offset] = at;
                at += NewSize(i, resultLocal);
            }
            start[body.Code.Length] = at;
            var bodyEnd = at;
            var handlerEnd = bodyEnd + exit.Length + 1;

            var o = new MemoryStream();
            o.Write(enter, 0, enter.Length);
            foreach (var i in instructions)
            {
                var end = start[i.Offset] + NewSize(i, resultLocal);
                if (i.Op == 0x2A)
                {
                    if (resultLocal is int r) Store(o, r);
                    o.WriteByte(0xDD);
                    Int(o, handlerEnd - (start[i.Offset] + (resultLocal is int rr ? StoreSize(rr) : 0) + 5));
                }
                else if (i.Op == 0xFE14)
                {
                    // `tail.` before a call that is followed by `ret`: a tail call cannot leave a
                    // protected region, so the prefix goes and the call is an ordinary one.
                }
                else if (IsShortBranch(i.Op))
                {
                    o.WriteByte((byte)(i.Op == 0xDE ? 0xDD : i.Op + 0x0D));
                    Int(o, Target(start, i, (sbyte)i.Operand[0]) - end);
                }
                else if (IsLongBranch(i.Op))
                {
                    o.WriteByte((byte)i.Op);
                    Int(o, Target(start, i, BitConverter.ToInt32(i.Operand, 0)) - end);
                }
                else if (i.Op == 0x45)
                {
                    o.WriteByte(0x45);
                    var n = BitConverter.ToInt32(i.Operand, 0);
                    Int(o, n);
                    for (var k = 0; k < n; k++)
                        Int(o, Target(start, i, BitConverter.ToInt32(i.Operand, 4 + 4 * k)) - end);
                }
                else
                {
                    if (i.Op > 0xFF) { o.WriteByte(0xFE); o.WriteByte((byte)(i.Op & 0xFF)); }
                    else o.WriteByte((byte)i.Op);
                    o.Write(i.Operand, 0, i.Operand.Length);
                }
            }
            o.Write(exit, 0, exit.Length);
            o.WriteByte(0xDC); // endfinally
            if (resultLocal is int load) Load(o, load);
            o.WriteByte(0x2A);

            var regions = body.Regions.ConvertAll(r => r with
            {
                TryOffset = start[r.TryOffset],
                TryLength = start[r.TryOffset + r.TryLength] - start[r.TryOffset],
                HandlerOffset = start[r.HandlerOffset],
                HandlerLength = start[r.HandlerOffset + r.HandlerLength] - start[r.HandlerOffset],
                ClassTokenOrFilter = r.Kind == ExceptionRegionKind.Filter
                    ? start[r.ClassTokenOrFilter] : r.ClassTokenOrFilter,
            });
            // Last, because a region enclosing others must follow them (ECMA-335 II.19).
            regions.Add(new Region(ExceptionRegionKind.Finally, enter.Length, bodyEnd - enter.Length,
                                   bodyEnd, exit.Length + 1, 0));
            return new Body(o.ToArray(), Math.Max(body.MaxStack, 1), localSignatureToken,
                            body.InitLocals || resultLocal != null, regions);
        }

        /// <summary>The body as a fat method body, 4-aligned for wherever it is put.</summary>
        public static byte[] Encode(Body body)
        {
            var o = new MemoryStream();
            var more = body.Regions.Count > 0;
            ushort flags = (ushort)(0x3 | (body.InitLocals ? 0x10 : 0) | (more ? 0x08 : 0) | (3 << 12));
            Short(o, flags);
            Short(o, (ushort)body.MaxStack);
            Int(o, body.Code.Length);
            Int(o, body.LocalSignatureToken);
            o.Write(body.Code, 0, body.Code.Length);
            if (more)
            {
                while (o.Length % 4 != 0) o.WriteByte(0);
                var size = 4 + 24 * body.Regions.Count;
                o.WriteByte(0x41); // an exception table, in the fat format
                o.WriteByte((byte)size); o.WriteByte((byte)(size >> 8)); o.WriteByte((byte)(size >> 16));
                foreach (var r in body.Regions)
                {
                    Int(o, r.Kind switch
                    {
                        ExceptionRegionKind.Catch => 0,
                        ExceptionRegionKind.Filter => 1,
                        ExceptionRegionKind.Finally => 2,
                        _ => 4,
                    });
                    Int(o, r.TryOffset); Int(o, r.TryLength);
                    Int(o, r.HandlerOffset); Int(o, r.HandlerLength);
                    Int(o, r.ClassTokenOrFilter);
                }
            }
            while (o.Length % 4 != 0) o.WriteByte(0);
            return o.ToArray();
        }

        internal sealed record Instruction(int Offset, int Op, byte[] Operand, int Size);

        /// <summary>Every instruction, by the operand size ECMA-335 III gives its opcode.</summary>
        internal static List<Instruction> Decode(byte[] code)
        {
            var found = new List<Instruction>();
            var at = 0;
            while (at < code.Length)
            {
                var offset = at;
                int op = code[at++];
                if (op == 0xFE) op = 0xFE00 | code[at++];
                var size = op == 0x45 ? 4 + 4 * BitConverter.ToInt32(code, at) : OperandSize(op);
                if (op == 0x27) throw new Unweavable("it uses `jmp`, which cannot leave a protected region");
                var operand = new byte[size];
                Array.Copy(code, at, operand, 0, size);
                at += size;
                found.Add(new Instruction(offset, op, operand, at - offset));
            }
            return found;
        }

        private static int OperandSize(int op)
        {
            if (op >= 0xFE00)
                return (op & 0xFF) switch
                {
                    0x06 or 0x07 or 0x15 or 0x16 or 0x1C => 4,
                    >= 0x09 and <= 0x0E => 2,
                    0x12 or 0x19 => 1,
                    _ => 0,
                };
            return op switch
            {
                >= 0x0E and <= 0x13 => 1,
                0x1F => 1,
                >= 0x2B and <= 0x37 => 1,
                0xDE => 1,
                0x21 or 0x23 => 8,
                0x20 or 0x22 or 0x27 or 0x28 or 0x29 => 4,
                >= 0x38 and <= 0x44 => 4,
                0x6F or 0x70 or 0x71 or 0x72 or 0x73 or 0x74 or 0x75 or 0x79 => 4,
                >= 0x7B and <= 0x81 => 4,
                0x8C or 0x8D or 0x8F or 0xA3 or 0xA4 or 0xA5 or 0xC2 or 0xC6 or 0xD0 or 0xDD => 4,
                _ => 0,
            };
        }

        private static bool IsShortBranch(int op) => op is (>= 0x2B and <= 0x37) or 0xDE;

        private static bool IsLongBranch(int op) => op is (>= 0x38 and <= 0x44) or 0xDD;

        private static int NewSize(Instruction i, int? resultLocal)
        {
            if (i.Op == 0x2A) return (resultLocal is int r ? StoreSize(r) : 0) + 5;
            if (i.Op == 0xFE14) return 0;
            if (IsShortBranch(i.Op)) return 5;
            return i.Size;
        }

        private static int Target(Dictionary<int, int> start, Instruction i, int relative)
        {
            var old = i.Offset + i.Size + relative;
            if (!start.TryGetValue(old, out var mapped))
                throw new Unweavable($"a branch at IL_{i.Offset:x4} lands inside an instruction");
            return mapped;
        }

        private static int StoreSize(int local) => local < 256 ? 2 : 4;

        private static void Store(Stream o, int local)
        {
            if (local < 256) { o.WriteByte(0x13); o.WriteByte((byte)local); }
            else { o.WriteByte(0xFE); o.WriteByte(0x0E); Short(o, (ushort)local); }
        }

        private static void Load(Stream o, int local)
        {
            if (local < 256) { o.WriteByte(0x11); o.WriteByte((byte)local); }
            else { o.WriteByte(0xFE); o.WriteByte(0x0C); Short(o, (ushort)local); }
        }

        internal static void Int(Stream o, int v)
        {
            o.WriteByte((byte)v); o.WriteByte((byte)(v >> 8));
            o.WriteByte((byte)(v >> 16)); o.WriteByte((byte)(v >> 24));
        }

        internal static void Short(Stream o, ushort v)
        {
            o.WriteByte((byte)v); o.WriteByte((byte)(v >> 8));
        }

        /// <summary><c>call</c> or <c>ldstr</c> and its token — five bytes.</summary>
        internal static byte[] Op(byte op, int token)
        {
            var o = new MemoryStream();
            o.WriteByte(op);
            Int(o, token);
            return o.ToArray();
        }
    }
}
