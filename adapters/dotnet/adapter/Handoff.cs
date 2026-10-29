using System;
using System.Threading;
using System.Threading.Tasks;

namespace PlumbSpec
{
    /// <summary>Which call a shim stands in for: the type, the member, and whether the call is
    /// static, on an instance (passed first) or a constructor (returning what it built).</summary>
    [AttributeUsage(AttributeTargets.Method)]
    internal sealed class StandsInForAttribute : Attribute
    {
        public StandsInForAttribute(Type type, string member, Call call = Call.Static)
        {
            Type = type;
            Member = member;
            Call = call;
        }

        public Type Type { get; }
        public string Member { get; }
        public Call Call { get; }
    }

    internal enum Call { Static, Instance, Constructor }

    /// <summary>
    /// The hand-off primitives, as the weave sees them: each call to one, in code the weave rewrote,
    /// is retargeted to the shim here that stands in for it (dev07-1-4-sr2).
    /// </summary>
    /// <remarks>
    /// <para>The JVM adapter weaves <c>Thread.start</c> and <c>ThreadPoolExecutor.execute</c> where they
    /// are defined. .NET's are defined in its own libraries, which are not in the copy and are not
    /// woven, so the aspect goes on the call instead: a short fixed list, matched on the call's exact
    /// signature, and anything else left as it was. A hand-off made inside a library is not seen
    /// here (dev07-1-4-u5); if its work reaches an entry point, the probe still reads that as sent
    /// elsewhere.</para>
    /// <para>Each shim has the target's signature exactly — an instance's receiver first, a
    /// constructor's result returned — so retargeting a call is one token and, for an instance or a
    /// constructor, the opcode: the stack is the same either way.</para>
    /// </remarks>
    public static class Handoff
    {
        [StandsInFor(typeof(Task), nameof(Task.Run))]
        public static Task Run(Action action) => Task.Run(Probe.Carry(action));

        [StandsInFor(typeof(Task), nameof(Task.Run))]
        public static Task Run(Action action, CancellationToken cancellation) =>
            Task.Run(Probe.Carry(action), cancellation);

        [StandsInFor(typeof(Task), nameof(Task.Run))]
        public static Task<T> Run<T>(Func<T> function) => Task.Run(Probe.Carry(function));

        [StandsInFor(typeof(Task), nameof(Task.Run))]
        public static Task<T> Run<T>(Func<T> function, CancellationToken cancellation) =>
            Task.Run(Probe.Carry(function), cancellation);

        [StandsInFor(typeof(Task), nameof(Task.Run))]
        public static Task Run(Func<Task> function) => Task.Run(Probe.Carry(function));

        [StandsInFor(typeof(Task), nameof(Task.Run))]
        public static Task Run(Func<Task> function, CancellationToken cancellation) =>
            Task.Run(Probe.Carry(function), cancellation);

        [StandsInFor(typeof(Task), nameof(Task.Run))]
        public static Task<T> Run<T>(Func<Task<T>> function) => Task.Run(Probe.Carry(function));

        [StandsInFor(typeof(Task), nameof(Task.Run))]
        public static Task<T> Run<T>(Func<Task<T>> function, CancellationToken cancellation) =>
            Task.Run(Probe.Carry(function), cancellation);

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task StartNew(TaskFactory factory, Action action) =>
            factory.StartNew(Probe.Carry(action));

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task StartNew(TaskFactory factory, Action action, CancellationToken cancellation) =>
            factory.StartNew(Probe.Carry(action), cancellation);

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task StartNew(TaskFactory factory, Action action, TaskCreationOptions options) =>
            factory.StartNew(Probe.Carry(action), options);

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task StartNew(TaskFactory factory, Action action, CancellationToken cancellation,
                                    TaskCreationOptions options, TaskScheduler scheduler) =>
            factory.StartNew(Probe.Carry(action), cancellation, options, scheduler);

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task StartNew(TaskFactory factory, Action<object?> action, object? state) =>
            factory.StartNew(Probe.Carry(action), state);

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task<T> StartNew<T>(TaskFactory factory, Func<T> function) =>
            factory.StartNew(Probe.Carry(function));

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task<T> StartNew<T>(TaskFactory factory, Func<T> function, CancellationToken cancellation) =>
            factory.StartNew(Probe.Carry(function), cancellation);

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task<T> StartNew<T>(TaskFactory factory, Func<T> function, TaskCreationOptions options) =>
            factory.StartNew(Probe.Carry(function), options);

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task<T> StartNew<T>(TaskFactory factory, Func<T> function, CancellationToken cancellation,
                                          TaskCreationOptions options, TaskScheduler scheduler) =>
            factory.StartNew(Probe.Carry(function), cancellation, options, scheduler);

        [StandsInFor(typeof(TaskFactory), nameof(TaskFactory.StartNew), Call.Instance)]
        public static Task<T> StartNew<T>(TaskFactory factory, Func<object?, T> function, object? state) =>
            factory.StartNew(Probe.Carry(function), state);

        [StandsInFor(typeof(Thread), ".ctor", Call.Constructor)]
        public static Thread NewThread(ThreadStart start)
        {
            var carried = Probe.Carry(new Action(start));
            return new Thread(() => carried());
        }

        [StandsInFor(typeof(Thread), ".ctor", Call.Constructor)]
        public static Thread NewThread(ThreadStart start, int maxStackSize)
        {
            var carried = Probe.Carry(new Action(start));
            return new Thread(() => carried(), maxStackSize);
        }

        [StandsInFor(typeof(Thread), ".ctor", Call.Constructor)]
        public static Thread NewThread(ParameterizedThreadStart start)
        {
            var carried = Probe.Carry(new Action<object?>(start));
            return new Thread(state => carried(state));
        }

        [StandsInFor(typeof(Thread), ".ctor", Call.Constructor)]
        public static Thread NewThread(ParameterizedThreadStart start, int maxStackSize)
        {
            var carried = Probe.Carry(new Action<object?>(start));
            return new Thread(state => carried(state), maxStackSize);
        }

        [StandsInFor(typeof(ThreadPool), nameof(ThreadPool.QueueUserWorkItem))]
        public static bool QueueUserWorkItem(WaitCallback callback)
        {
            var carried = Probe.Carry(new Action<object?>(callback));
            return ThreadPool.QueueUserWorkItem(state => carried(state));
        }

        [StandsInFor(typeof(ThreadPool), nameof(ThreadPool.QueueUserWorkItem))]
        public static bool QueueUserWorkItem(WaitCallback callback, object? state)
        {
            var carried = Probe.Carry(new Action<object?>(callback));
            return ThreadPool.QueueUserWorkItem(s => carried(s), state);
        }

        [StandsInFor(typeof(ThreadPool), nameof(ThreadPool.QueueUserWorkItem))]
        public static bool QueueUserWorkItem<T>(Action<T> callback, T state, bool preferLocal) =>
            ThreadPool.QueueUserWorkItem(Probe.Carry(callback), state, preferLocal);

        [StandsInFor(typeof(ThreadPool), nameof(ThreadPool.UnsafeQueueUserWorkItem))]
        public static bool UnsafeQueueUserWorkItem(WaitCallback callback, object? state)
        {
            // The unsafe queue carries no flow, which is why the window is carried by hand.
            var carried = Probe.Carry(new Action<object?>(callback));
            return ThreadPool.UnsafeQueueUserWorkItem(s => carried(s), state);
        }
    }
}
