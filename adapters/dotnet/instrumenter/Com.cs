using System;
using System.Runtime.InteropServices;

namespace PlumbSpec.Instrumenter
{
    /// <summary>
    /// The engine's side of COM, by hand: an object is a pointer to a table of function pointers,
    /// in the order the IDL declares them. One instance of each, never freed — the engine holds
    /// them for the life of the process — so reference counting is a constant.
    /// </summary>
    internal static unsafe class Com
    {
        public const int S_OK = 0, S_FALSE = 1;
        public const int E_NOINTERFACE = unchecked((int)0x80004002);
        public const int CLASS_E_CLASSNOTAVAILABLE = unchecked((int)0x80040111);

        public static readonly Guid IUnknown = new("00000000-0000-0000-C000-000000000046");
        public static readonly Guid IClassFactory = new("00000001-0000-0000-C000-000000000046");

        /// <summary>A COM object whose table is <paramref name="table"/>.</summary>
        public static void* Object(void*[] table)
        {
            var vtable = (void**)NativeMemory.Alloc((nuint)(table.Length * sizeof(void*)));
            for (var i = 0; i < table.Length; i++) vtable[i] = table[i];
            var instance = (void**)NativeMemory.Alloc((nuint)sizeof(void*));
            *instance = vtable;
            return instance;
        }

        /// <summary>The <paramref name="slot"/>th entry of an object's table.</summary>
        public static void* Slot(void* instance, int slot) => (*(void***)instance)[slot];

        [UnmanagedCallersOnly]
        public static uint AddRef(void* self) => 1;

        [UnmanagedCallersOnly]
        public static uint Release(void* self) => 1;
    }
}
