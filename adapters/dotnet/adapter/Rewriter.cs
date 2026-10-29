using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.IO;
using System.Linq;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Text;

namespace PlumbSpec
{
    /// <summary>
    /// One assembly, rewritten by appending and never by re-encoding (dev07-1-3-sr12).
    /// </summary>
    /// <remarks>
    /// <para>The runtime's own reader reads it; this writes. Every heap grows only at its end and every
    /// table only after its last row, so each offset, row number and token the assembly already
    /// holds still means what it meant, and nothing that refers to one has to be found and fixed. A
    /// woven method keeps its row; its RVA points at a new body. The new bodies and the new metadata
    /// go into one section added to the image, and the CLI header points at the new metadata.</para>
    /// <para>What appending cannot do is change how wide an index is. Where a new row or a longer heap
    /// would cross a width, the assembly is refused by name and left as built (dev07-1-3-nfr3) —
    /// re-encoding every table is the general answer, and it is not written yet.</para>
    /// </remarks>
    internal sealed class Rewriter
    {
        internal sealed class Refused : Exception
        {
            public Refused(string why) : base(why) { }
        }

        private readonly byte[] image;
        public readonly PEReader Pe;
        public readonly MetadataReader Md;
        private readonly int sectionRva;
        private readonly MemoryStream bodies = new MemoryStream();
        private readonly Dictionary<int, int> newRva = new Dictionary<int, int>();

        private readonly MemoryStream strings = new MemoryStream(), blobs = new MemoryStream(),
                                      userStrings = new MemoryStream();
        private readonly int stringsBase, blobsBase, userStringsBase;
        private readonly Dictionary<string, int> stringOffsets = new Dictionary<string, int>();

        private readonly List<(ushort[] Version, int Name)> assemblyRefs = new List<(ushort[], int)>();
        private readonly List<(int Scope, int Name, int Namespace)> typeRefs = new List<(int, int, int)>();
        private readonly List<(int Parent, int Name, int Signature)> memberRefs = new List<(int, int, int)>();
        private readonly List<int> standAloneSigs = new List<int>();

        public Rewriter(byte[] image)
        {
            this.image = image;
            Pe = new PEReader(ImmutableArray.Create(image));
            if (!Pe.HasMetadata) throw new Refused("it is not a .NET assembly");
            var cor = Pe.PEHeaders.CorHeader!;
            if ((cor.Flags & CorFlags.ILOnly) == 0)
                throw new Refused("it is mixed-mode, holding native code beside its IL");
            if (cor.ManagedNativeHeaderDirectory.Size != 0)
                throw new Refused("it is ReadyToRun, so the runtime would run its precompiled code " +
                                  "and never the woven IL");
            Md = Pe.GetMetadataReader();
            // From the stream headers, which count a heap's padding, because what is appended goes
            // after the padding: the reader's own heap sizes do not, and every new name would be
            // read from a few bytes too early.
            var streams = Streams(Pe.PEHeaders.MetadataStartOffset);
            int Size(string name) => streams.FirstOrDefault(s => s.Name == name)?.Size ?? 0;
            stringsBase = Size("#Strings");
            blobsBase = Size("#Blob");
            // An assembly with no literal has no user-string heap, which begins with an empty entry.
            userStringsBase = Math.Max(Size("#US"), 1);
            var align = Pe.PEHeaders.PEHeader!.SectionAlignment;
            sectionRva = Pe.PEHeaders.SectionHeaders
                .Max(s => s.VirtualAddress + Align(Math.Max(s.VirtualSize, s.SizeOfRawData), align));
        }

        // ---- heaps ----

        public int String(string value)
        {
            if (stringOffsets.TryGetValue(value, out var known)) return known;
            var at = stringsBase + (int)strings.Length;
            var bytes = Encoding.UTF8.GetBytes(value);
            strings.Write(bytes, 0, bytes.Length);
            strings.WriteByte(0);
            return stringOffsets[value] = at;
        }

        public int Blob(byte[] value)
        {
            var at = blobsBase + (int)blobs.Length;
            Compressed(blobs, value.Length);
            blobs.Write(value, 0, value.Length);
            return at;
        }

        /// <summary>A literal for <c>ldstr</c>, as its token.</summary>
        public int UserString(string value)
        {
            var at = userStringsBase + (int)userStrings.Length;
            var bytes = Encoding.Unicode.GetBytes(value);
            Compressed(userStrings, bytes.Length + 1);
            userStrings.Write(bytes, 0, bytes.Length);
            // ECMA-335 II.24.2.4: 1 when any character needs more than its low byte to compare.
            userStrings.WriteByte((byte)(value.Any(c => c > 0x7E || (c >= 0x01 && c <= 0x08) ||
                (c >= 0x0E && c <= 0x1F) || c == 0x27 || c == 0x2D) ? 1 : 0));
            return 0x70000000 | at;
        }

        // ---- rows; each returns its token, which is final the moment it is made ----

        public int AssemblyRef(string name, Version version)
        {
            assemblyRefs.Add((new[] { (ushort)version.Major, (ushort)version.Minor,
                                      (ushort)Math.Max(version.Build, 0), (ushort)Math.Max(version.Revision, 0) },
                              String(name)));
            return 0x23000000 | (Md.GetTableRowCount(TableIndex.AssemblyRef) + assemblyRefs.Count);
        }

        public int TypeRef(int assemblyRefToken, string ns, string name)
        {
            typeRefs.Add((assemblyRefToken & 0xFFFFFF, String(name), String(ns)));
            return 0x01000000 | (Md.GetTableRowCount(TableIndex.TypeRef) + typeRefs.Count);
        }

        public int MemberRef(int typeRefToken, string name, byte[] signature)
        {
            memberRefs.Add((typeRefToken & 0xFFFFFF, String(name), Blob(signature)));
            return 0x0A000000 | (Md.GetTableRowCount(TableIndex.MemberRef) + memberRefs.Count);
        }

        public int StandAloneSig(byte[] signature)
        {
            standAloneSigs.Add(Blob(signature));
            return 0x11000000 | (Md.GetTableRowCount(TableIndex.StandAloneSig) + standAloneSigs.Count);
        }

        public void SetBody(MethodDefinitionHandle method, byte[] encoded)
        {
            newRva[MetadataTokens.GetRowNumber(method)] = sectionRva + (int)bodies.Length;
            bodies.Write(encoded, 0, encoded.Length);
        }

        public bool Changed => newRva.Count > 0;

        // ---- the image ----

        public byte[] Build()
        {
            var metadata = BuildMetadata();
            var pe = Pe.PEHeaders;
            var header = pe.PEHeader!;
            var content = new MemoryStream();
            bodies.WriteTo(content);
            while (content.Length % 4 != 0) content.WriteByte(0);
            var metadataRva = sectionRva + (int)content.Length;
            content.Write(metadata, 0, metadata.Length);

            var sectionTable = pe.PEHeaderStartOffset + pe.CoffHeader.SizeOfOptionalHeader;
            var sections = pe.SectionHeaders.Length;
            var headerEnd = sectionTable + (sections + 1) * 40;
            var source = image;
            // Everything after the headers moves down the file by this much, the CLI header with it.
            var moved = 0;
            if (headerEnd > header.SizeOfHeaders)
            {
                moved = Align(headerEnd, header.FileAlignment) - header.SizeOfHeaders;
                source = WidenHeaders(moved);
            }

            var rawStart = Align(source.Length, header.FileAlignment);
            var rawSize = Align((int)content.Length, header.FileAlignment);
            var o = new byte[rawStart + rawSize];
            source.CopyTo(o, 0);
            content.ToArray().CopyTo(o, rawStart);

            Put16(o, pe.CoffHeaderStartOffset + 2, (ushort)(sections + 1));
            Put32(o, pe.PEHeaderStartOffset + 56,
                  Align(sectionRva + (int)content.Length, header.SectionAlignment)); // SizeOfImage
            Put32(o, pe.PEHeaderStartOffset + 64, 0);                             // CheckSum
            // The certificate, if any, signed the bytes this replaces; it is removed rather than left
            // to vouch for an image it never saw.
            var directories = pe.PEHeaderStartOffset + (header.Magic == PEMagic.PE32Plus ? 112 : 96);
            Put32(o, directories + 4 * 8, 0);
            Put32(o, directories + 4 * 8 + 4, 0);

            var s = sectionTable + sections * 40;
            Encoding.ASCII.GetBytes(".plumb\0\0").CopyTo(o, s);
            Put32(o, s + 8, (int)content.Length);
            Put32(o, s + 12, sectionRva);
            Put32(o, s + 16, rawSize);
            Put32(o, s + 20, rawStart);
            Put32(o, s + 36, unchecked((int)0x40000040)); // initialized data, readable

            Put32(o, pe.CorHeaderStartOffset + moved + 8, metadataRva);
            Put32(o, pe.CorHeaderStartOffset + moved + 12, metadata.Length);
            return o;
        }

        /// <summary>
        /// The image with its headers <paramref name="by"/> bytes longer, so another section header
        /// fits — Roslyn leaves none to spare. Every section's bytes move down the file and none
        /// moves in memory, so no RVA changes; what names a file offset is each section's
        /// <c>PointerToRawData</c> and each debug directory entry's, and both move with it.
        /// </summary>
        private byte[] WidenHeaders(int by)
        {
            var pe = Pe.PEHeaders;
            var header = pe.PEHeader!;
            if (header.SizeOfHeaders + by > pe.SectionHeaders.Min(s => s.VirtualAddress))
                throw new Refused("its headers leave no room for another section, and its first " +
                                  "section sits too close to them to make any");
            var o = new byte[image.Length + by];
            Array.Copy(image, 0, o, 0, header.SizeOfHeaders);
            Array.Copy(image, header.SizeOfHeaders, o, header.SizeOfHeaders + by,
                       image.Length - header.SizeOfHeaders);
            Put32(o, pe.PEHeaderStartOffset + 60, header.SizeOfHeaders + by); // SizeOfHeaders
            var sectionTable = pe.PEHeaderStartOffset + pe.CoffHeader.SizeOfOptionalHeader;
            for (var i = 0; i < pe.SectionHeaders.Length; i++)
                if (pe.SectionHeaders[i].PointerToRawData != 0)
                    Put32(o, sectionTable + i * 40 + 20, pe.SectionHeaders[i].PointerToRawData + by);
            var debug = header.DebugTableDirectory;
            if (debug.Size > 0 && pe.TryGetDirectoryOffset(debug, out var at))
                for (var entry = at + by; entry < at + by + debug.Size; entry += 28)
                {
                    var raw = BitConverter.ToInt32(o, entry + 24);
                    if (raw != 0) Put32(o, entry + 24, raw + by);
                }
            return o;
        }

        private byte[] BuildMetadata()
        {
            var root = Pe.PEHeaders.MetadataStartOffset;
            var streams = Streams(root);
            if (!streams.Any(s => s.Name == "#~"))
                throw new Refused("its metadata is the uncompressed form a compiler writes for " +
                                  "edit-and-continue");
            var tables = streams.First(s => s.Name == "#~");
            var heapSizes = image[root + tables.Offset + 6];
            var valid = BitConverter.ToUInt64(image, root + tables.Offset + 8);
            var sorted = BitConverter.ToUInt64(image, root + tables.Offset + 16);

            var before = new int[64];
            var after = new int[64];
            for (var t = 0; t < 64; t++)
                before[t] = after[t] = (valid & (1UL << t)) != 0 ? Md.GetTableRowCount((TableIndex)t) : 0;
            after[0x23] += assemblyRefs.Count;
            after[0x01] += typeRefs.Count;
            after[0x0A] += memberRefs.Count;
            after[0x11] += standAloneSigs.Count;
            if (!Widths(before).SequenceEqual(Widths(after)))
                throw new Refused("the rows the weave adds would widen its metadata's indexes, which " +
                                  "this writer does not do yet");
            if (Crosses(heapSizes, 0x01, stringsBase, strings.Length) ||
                Crosses(heapSizes, 0x04, blobsBase, blobs.Length))
                throw new Refused("the weave would grow a heap past the size its indexes can address");

            var stringIndex = (heapSizes & 0x01) != 0 ? 4 : 2;
            var blobIndex = (heapSizes & 0x04) != 0 ? 4 : 2;
            var scope = Coded(after, 2, 0x00, 0x1A, 0x23, 0x01);
            var parent = Coded(after, 3, 0x02, 0x01, 0x1A, 0x06, 0x1B);
            Expect(TableIndex.TypeRef, scope + 2 * stringIndex);
            Expect(TableIndex.MemberRef, parent + stringIndex + blobIndex);
            Expect(TableIndex.AssemblyRef, 12 + 2 * blobIndex + 2 * stringIndex);
            Expect(TableIndex.StandAloneSig, blobIndex);

            var newValid = valid;
            for (var t = 0; t < 64; t++) if (after[t] > 0) newValid |= 1UL << t;

            var o = new MemoryStream();
            o.Write(image, root + tables.Offset, 8);
            o.Write(BitConverter.GetBytes(newValid), 0, 8);
            o.Write(BitConverter.GetBytes(sorted), 0, 8);
            for (var t = 0; t < 64; t++) if ((newValid & (1UL << t)) != 0) Il.Int(o, after[t]);
            var rowCountEnd = root + tables.Offset + 24 + 4 * System.Numerics.BitOperations.PopCount(valid);
            if ((heapSizes & 0x40) != 0) o.Write(image, rowCountEnd, 4);

            for (var t = 0; t < 64; t++)
            {
                if (before[t] > 0)
                {
                    var table = (TableIndex)t;
                    var size = Md.GetTableRowSize(table);
                    var data = new byte[before[t] * size];
                    Array.Copy(image, root + Md.GetTableMetadataOffset(table), data, 0, data.Length);
                    if (table == TableIndex.MethodDef)
                        foreach (var (row, rva) in newRva) Put32(data, (row - 1) * size, rva);
                    o.Write(data, 0, data.Length);
                }
                switch (t)
                {
                    case 0x01:
                        foreach (var (s, name, ns) in typeRefs)
                        {
                            Index(o, (s << 2) | 2, scope); // AssemblyRef is ResolutionScope tag 2
                            Index(o, name, stringIndex); Index(o, ns, stringIndex);
                        }
                        break;
                    case 0x0A:
                        foreach (var (p, name, sig) in memberRefs)
                        {
                            Index(o, (p << 3) | 1, parent); // TypeRef is MemberRefParent tag 1
                            Index(o, name, stringIndex); Index(o, sig, blobIndex);
                        }
                        break;
                    case 0x11:
                        foreach (var sig in standAloneSigs) Index(o, sig, blobIndex);
                        break;
                    case 0x23:
                        foreach (var (v, name) in assemblyRefs)
                        {
                            foreach (var part in v) Il.Short(o, part);
                            Il.Int(o, 0);                 // flags: no public key
                            Index(o, 0, blobIndex);       // public key or token
                            Index(o, name, stringIndex);
                            Index(o, 0, stringIndex);     // culture: neutral
                            Index(o, 0, blobIndex);       // hash
                        }
                        break;
                }
            }
            while (o.Length % 4 != 0) o.WriteByte(0);
            var newTables = o.ToArray();

            if (userStrings.Length > 0 && !streams.Any(s => s.Name == "#US"))
                streams.Add(new Stream("#US", -1, 0));
            var contents = new List<(string Name, byte[] Data)>();
            foreach (var s in streams)
            {
                var original = s.Offset < 0 ? new byte[] { 0 } : new byte[s.Size];
                if (s.Offset >= 0) Array.Copy(image, root + s.Offset, original, 0, s.Size);
                contents.Add((s.Name, s.Name switch
                {
                    "#~" => newTables,
                    "#Strings" => Padded(original, strings),
                    "#Blob" => Padded(original, blobs),
                    "#US" => Padded(original, userStrings),
                    _ => original,
                }));
            }
            return Root(root, contents);
        }

        // ---- the metadata root and its streams ----

        private sealed record Stream(string Name, int Offset, int Size);

        private List<Stream> Streams(int root)
        {
            var versionLength = BitConverter.ToInt32(image, root + 12);
            var at = root + 16 + versionLength + 2;
            var count = BitConverter.ToUInt16(image, at);
            at += 2;
            var found = new List<Stream>();
            for (var i = 0; i < count; i++)
            {
                var offset = BitConverter.ToInt32(image, at);
                var size = BitConverter.ToInt32(image, at + 4);
                var end = Array.IndexOf(image, (byte)0, at + 8);
                found.Add(new Stream(Encoding.ASCII.GetString(image, at + 8, end - at - 8), offset, size));
                at = at + 8 + Align(end - at - 8 + 1, 4);
            }
            return found;
        }

        private byte[] Root(int root, List<(string Name, byte[] Data)> streams)
        {
            var versionLength = BitConverter.ToInt32(image, root + 12);
            var head = new MemoryStream();
            head.Write(image, root, 16 + versionLength + 2); // signature, versions, version string, flags
            Il.Short(head, (ushort)streams.Count);
            var headersSize = streams.Sum(s => 8 + Align(s.Name.Length + 1, 4));
            var offset = (int)head.Length + headersSize;
            foreach (var (name, data) in streams)
            {
                Il.Int(head, offset);
                Il.Int(head, data.Length);
                var bytes = Encoding.ASCII.GetBytes(name);
                head.Write(bytes, 0, bytes.Length);
                for (var i = bytes.Length; i < Align(bytes.Length + 1, 4); i++) head.WriteByte(0);
                offset += data.Length;
            }
            foreach (var (_, data) in streams) head.Write(data, 0, data.Length);
            return head.ToArray();
        }

        private static byte[] Padded(byte[] original, MemoryStream appended)
        {
            var o = new MemoryStream();
            o.Write(original, 0, original.Length);
            appended.WriteTo(o);
            while (o.Length % 4 != 0) o.WriteByte(0);
            return o.ToArray();
        }

        // ---- index widths (ECMA-335 II.24.2.6) ----

        /// <summary>Every index width a row the weave adds can change: the four grown tables' own,
        /// and each coded index any of them is a member of.</summary>
        private static int[] Widths(int[] rows) => new[]
        {
            rows[0x01] < 0x10000 ? 2 : 4, rows[0x0A] < 0x10000 ? 2 : 4,
            rows[0x11] < 0x10000 ? 2 : 4, rows[0x23] < 0x10000 ? 2 : 4,
            Coded(rows, 2, 0x02, 0x01, 0x1B),                                  // TypeDefOrRef
            Coded(rows, 5, 0x06, 0x04, 0x01, 0x02, 0x08, 0x09, 0x0A, 0x00, 0x0E, 0x17, 0x14, 0x11,
                  0x1A, 0x1B, 0x20, 0x23, 0x26, 0x27, 0x28, 0x2A, 0x2C, 0x2B),  // HasCustomAttribute
            Coded(rows, 3, 0x02, 0x01, 0x1A, 0x06, 0x1B),                      // MemberRefParent
            Coded(rows, 1, 0x06, 0x0A),                                        // MethodDefOrRef
            Coded(rows, 3, 0x06, 0x0A),                                        // CustomAttributeType
            Coded(rows, 2, 0x26, 0x23, 0x27),                                  // Implementation
            Coded(rows, 2, 0x00, 0x1A, 0x23, 0x01),                            // ResolutionScope
        };

        private static int Coded(int[] rows, int tagBits, params int[] tables) =>
            tables.Max(t => rows[t]) < (1 << (16 - tagBits)) ? 2 : 4;

        private static bool Crosses(byte heapSizes, byte bit, int start, long grown) =>
            (heapSizes & bit) == 0 && start + grown >= 0x10000;

        private void Expect(TableIndex table, int size)
        {
            if (Md.GetTableRowCount(table) > 0 && Md.GetTableRowSize(table) != size)
                throw new Refused($"its {table} rows are {Md.GetTableRowSize(table)} bytes where this " +
                                  $"writer computes {size}, so it does not understand the layout");
        }

        private static void Index(System.IO.Stream o, int value, int width)
        {
            if (width == 2) Il.Short(o, (ushort)value);
            else Il.Int(o, value);
        }

        private static void Compressed(System.IO.Stream o, int value)
        {
            if (value < 0x80) o.WriteByte((byte)value);
            else if (value < 0x4000) { o.WriteByte((byte)(0x80 | (value >> 8))); o.WriteByte((byte)value); }
            else
            {
                o.WriteByte((byte)(0xC0 | (value >> 24))); o.WriteByte((byte)(value >> 16));
                o.WriteByte((byte)(value >> 8)); o.WriteByte((byte)value);
            }
        }

        private static int Align(int value, int to) => (value + to - 1) / to * to;

        private static void Put16(byte[] o, int at, ushort v) { o[at] = (byte)v; o[at + 1] = (byte)(v >> 8); }

        private static void Put32(byte[] o, int at, int v)
        {
            o[at] = (byte)v; o[at + 1] = (byte)(v >> 8); o[at + 2] = (byte)(v >> 16); o[at + 3] = (byte)(v >> 24);
        }
    }
}
