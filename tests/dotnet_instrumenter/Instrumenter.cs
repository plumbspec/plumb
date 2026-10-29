using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace PlumbSpec.Instrumenter
{
    /// <summary>
    /// The engine's entry into the library (CLRInstrumentationEngine, InstrumentationMethod.cpp):
    /// <c>DllGetClassObject</c> for an <c>IClassFactory</c>, which makes the
    /// <c>IInstrumentationMethod</c>.
    /// </summary>
    internal static unsafe class Exports
    {
        /// <summary>Plumb's instrumentation method, as the config names it.</summary>
        public static readonly Guid Class = new("6C1E2B0A-6F5D-4E4B-9C1D-5B1A7E3F2A10");

        private static readonly Guid IInstrumentationMethod = new("0D92A8D9-6645-4803-B94B-06A1C4F4E633");

        private static void* factory, method;

        [UnmanagedCallersOnly(EntryPoint = "DllGetClassObject")]
        public static int DllGetClassObject(Guid* clsid, Guid* iid, void** result)
        {
            *result = null;
            if (*clsid != Class) return Com.CLASS_E_CLASSNOTAVAILABLE;
            if (*iid != Com.IClassFactory && *iid != Com.IUnknown) return Com.E_NOINTERFACE;
            factory = factory != null ? factory : Com.Object(new void*[]
            {
                (delegate* unmanaged<void*, Guid*, void**, int>)&FactoryQueryInterface,
                (delegate* unmanaged<void*, uint>)&Com.AddRef,
                (delegate* unmanaged<void*, uint>)&Com.Release,
                (delegate* unmanaged<void*, void*, Guid*, void**, int>)&CreateInstance,
                (delegate* unmanaged<void*, int, int>)&LockServer,
            });
            *result = factory;
            Log.Say("factory");
            return Com.S_OK;
        }

        [UnmanagedCallersOnly]
        private static int FactoryQueryInterface(void* self, Guid* iid, void** result)
        {
            if (*iid == Com.IClassFactory || *iid == Com.IUnknown) { *result = self; return Com.S_OK; }
            *result = null;
            return Com.E_NOINTERFACE;
        }

        [UnmanagedCallersOnly]
        private static int CreateInstance(void* self, void* outer, Guid* iid, void** result)
        {
            *result = null;
            if (*iid != IInstrumentationMethod && *iid != Com.IUnknown) return Com.E_NOINTERFACE;
            method = method != null ? method : Com.Object(InstrumentationMethod.Table());
            *result = method;
            return Com.S_OK;
        }

        [UnmanagedCallersOnly]
        private static int LockServer(void* self, int lockIt) => Com.S_OK;

        [UnmanagedCallersOnly]
        public static int MethodQueryInterface(void* self, Guid* iid, void** result)
        {
            if (*iid == IInstrumentationMethod || *iid == Com.IUnknown) { *result = self; return Com.S_OK; }
            *result = null;
            return Com.E_NOINTERFACE;
        }
    }

    /// <summary><c>IInstrumentationMethod</c>, slot for slot as InstrumentationEngine.idl declares it.</summary>
    internal static unsafe class InstrumentationMethod
    {
        private static int modules;

        public static void*[] Table() => new void*[]
        {
            (delegate* unmanaged<void*, Guid*, void**, int>)&Exports.MethodQueryInterface,
            (delegate* unmanaged<void*, uint>)&Com.AddRef,
            (delegate* unmanaged<void*, uint>)&Com.Release,
            (delegate* unmanaged<void*, void*, int>)&Initialize,
            (delegate* unmanaged<void*, void*, int>)&Ignored,          // OnAppDomainCreated
            (delegate* unmanaged<void*, void*, int>)&Ignored,          // OnAppDomainShutdown
            (delegate* unmanaged<void*, void*, int>)&Ignored,          // OnAssemblyLoaded
            (delegate* unmanaged<void*, void*, int>)&Ignored,          // OnAssemblyUnloaded
            (delegate* unmanaged<void*, void*, int>)&OnModuleLoaded,
            (delegate* unmanaged<void*, void*, int>)&Ignored,          // OnModuleUnloaded
            (delegate* unmanaged<void*, int>)&OnShutdown,
            (delegate* unmanaged<void*, void*, int, int*, int>)&ShouldInstrumentMethod,
            (delegate* unmanaged<void*, void*, int, int>)&Ignored2,    // BeforeInstrumentMethod
            (delegate* unmanaged<void*, void*, int, int>)&InstrumentMethod,
            (delegate* unmanaged<void*, void*, int, int>)&Ignored2,    // OnInstrumentationComplete
            (delegate* unmanaged<void*, void*, void*, int*, int>)&AllowInlineSite,
        };

        [UnmanagedCallersOnly]
        private static int Initialize(void* self, void* profilerManager)
        {
            Log.Say("initialize");
            return Com.S_OK;
        }

        [UnmanagedCallersOnly]
        private static int OnModuleLoaded(void* self, void* module)
        {
            Interlocked.Increment(ref modules);
            return Com.S_OK;
        }

        [UnmanagedCallersOnly]
        private static int OnShutdown(void* self)
        {
            Log.Say($"shutdown modules={modules}");
            return Com.S_OK;
        }

        [UnmanagedCallersOnly]
        private static int ShouldInstrumentMethod(void* self, void* method, int isRejit, int* instrument)
        {
            *instrument = 0;
            try { *instrument = Weave.Wanted(method) ? 1 : 0; }
            catch (Exception failed) { Log.Say($"failed {failed.Message}"); }
            return Com.S_OK;
        }

        /// <summary>A failure costs the method its probe and never the run (dev07-1-3-nfr2): it is
        /// said, and the method is compiled as it was.</summary>
        [UnmanagedCallersOnly]
        private static int InstrumentMethod(void* self, void* method, int isRejit)
        {
            try { Weave.Instrument(method); }
            catch (Exception failed) { Log.Say($"failed {failed.Message}"); }
            return Com.S_OK;
        }

        [UnmanagedCallersOnly]
        private static int AllowInlineSite(void* self, void* inlinee, void* caller, int* allow)
        {
            *allow = 1;
            return Com.S_OK;
        }

        [UnmanagedCallersOnly]
        private static int Ignored(void* self, void* argument) => Com.S_OK;

        [UnmanagedCallersOnly]
        private static int Ignored2(void* self, void* argument, int flag) => Com.S_OK;
    }

    /// <summary>What the prototype test reads: one line per event, to the file it names.</summary>
    internal static class Log
    {
        private static readonly object Gate = new();

        public static void Say(string line)
        {
            var path = Environment.GetEnvironmentVariable("PLUMB_INSTRUMENTER_LOG");
            if (string.IsNullOrEmpty(path)) return;
            lock (Gate) File.AppendAllText(path, line + "\n");
        }
    }
}
