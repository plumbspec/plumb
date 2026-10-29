using System;
using System.IO;

namespace PlumbSpec
{
    /// <summary>The pieces of ECMA-335 II.23.2 the weave reads and writes by hand.</summary>
    internal static class Signature
    {
        public static int Compressed(byte[] b, ref int at)
        {
            var first = b[at];
            if ((first & 0x80) == 0) { at += 1; return first; }
            if ((first & 0xC0) == 0x80) { at += 2; return ((first & 0x3F) << 8) | b[at - 1]; }
            at += 4;
            return ((first & 0x1F) << 24) | (b[at - 3] << 16) | (b[at - 2] << 8) | b[at - 1];
        }

        public static void WriteCompressed(Stream o, int value)
        {
            if (value < 0x80) o.WriteByte((byte)value);
            else if (value < 0x4000) { o.WriteByte((byte)(0x80 | (value >> 8))); o.WriteByte((byte)value); }
            else
            {
                o.WriteByte((byte)(0xC0 | (value >> 24))); o.WriteByte((byte)(value >> 16));
                o.WriteByte((byte)(value >> 8)); o.WriteByte((byte)value);
            }
        }

        /// <summary>One type in a signature (II.23.2.12), so its bytes can be copied whole.</summary>
        public static void SkipType(byte[] b, ref int at)
        {
            while (b[at] == 0x1F || b[at] == 0x20) { at++; Compressed(b, ref at); }
            var element = b[at++];
            switch (element)
            {
                case >= 0x01 and <= 0x0E:
                case 0x16: case 0x18: case 0x19: case 0x1C:
                    return;
                case 0x0F: case 0x10: case 0x1D: case 0x45:
                    SkipType(b, ref at);
                    return;
                case 0x11: case 0x12: case 0x13: case 0x1E:
                    Compressed(b, ref at);
                    return;
                case 0x14:
                    SkipType(b, ref at);
                    Compressed(b, ref at);
                    var sizes = Compressed(b, ref at);
                    for (var i = 0; i < sizes; i++) Compressed(b, ref at);
                    var bounds = Compressed(b, ref at);
                    for (var i = 0; i < bounds; i++) Compressed(b, ref at);
                    return;
                case 0x15:
                    at++;
                    Compressed(b, ref at);
                    var arguments = Compressed(b, ref at);
                    for (var i = 0; i < arguments; i++) SkipType(b, ref at);
                    return;
                case 0x1B:
                    var convention = b[at++];
                    if ((convention & 0x10) != 0) Compressed(b, ref at);
                    var parameters = Compressed(b, ref at);
                    SkipType(b, ref at);
                    for (var i = 0; i < parameters; i++)
                    {
                        if (b[at] == 0x41) at++;
                        SkipType(b, ref at);
                    }
                    return;
                default:
                    throw new Il.Unweavable($"a signature holds an element 0x{element:x2} this writer does not read");
            }
        }
    }
}
