using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection.Metadata;

namespace PlumbSpec
{
    /// <summary>
    /// Method bodies, read and decoded by the operand size ECMA-335 III gives each opcode — so the
    /// planner can see which calls a method makes.
    /// </summary>
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
    }
}
