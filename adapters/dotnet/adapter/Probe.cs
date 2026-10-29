using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading;

namespace PlumbSpec
{
    /// <summary>
    /// What woven code calls. Production reports that it ran, an entry point that it was entered and
    /// left, and a test that it began — and the collector reads the test's scope when it ends.
    /// </summary>
    /// <remarks>
    /// <para>The scope rides the test's own logical flow (dev07-1-3-sr05): an <c>AsyncLocal</c> set by
    /// the test's first instruction, which .NET carries into whatever the test awaits, starts or
    /// queues. That is what keeps two tests xUnit runs at once apart (dev07-1-3-sr13), and why a
    /// test's window cannot be opened from VSTest's own callbacks, which arrive on another thread
    /// than the test runs on under xUnit and NUnit — measured.</para>
    /// <para>Public, because woven code in somebody else's assembly calls it; nothing else should.
    /// Every member is cheap and none throws: it runs inside their production code.</para>
    /// </remarks>
    public static class Probe
    {
        private static readonly AsyncLocal<Scope?> Current = new AsyncLocal<Scope?>();

        /// <summary>Set inside work a seen hand-off carried, and carried on with it across its own
        /// awaits: the flow is the test's work, and no longer the test's own (dev07-1-4-ur1.5).</summary>
        private static readonly AsyncLocal<bool> Hopped = new AsyncLocal<bool>();

        /// <summary>
        /// The test whose own flow this thread is resuming, while a woven async step runs here.
        /// </summary>
        /// <remarks>
        /// .NET carries a test's flow to every thread it reaches — across an await, and equally
        /// across a hand-off nobody saw — so the flow alone cannot say whether the test is still
        /// the one running. The test's own thread can, and so can a step of the project's own async
        /// code resuming that flow: an await, not a hand-off (dev07-1-3-sr05). Anything else reaching
        /// an entry point is somewhere the test sent work, and reads as that (dev07-1-4-sr4).
        /// </remarks>
        [ThreadStatic] private static Scope? resumed;

        [ThreadStatic] private static int resuming;

        /// <summary>
        /// The entry points this flow is inside, innermost first — the window (dev07-1-4-sr1).
        /// </summary>
        /// <remarks>
        /// Per logical flow, not per thread (dev07-1-3-sr05). An entry point pushes on entry and its
        /// <c>finally</c> pops, so a synchronous one is a window exactly as long as its call. An async
        /// one's <c>finally</c> runs when it first yields, and pops the window only from the caller's
        /// flow: the work it awaits captured the flow with the window open, and keeps it open until
        /// that work is done, on whichever thread resumes it.
        /// </remarks>
        private static readonly AsyncLocal<Window?> Open = new AsyncLocal<Window?>();

        private sealed record Window(Window? Outer, string EntryPoint);

        private static readonly ConcurrentDictionary<string, ConcurrentQueue<Scope>> Begun =
            new ConcurrentDictionary<string, ConcurrentQueue<Scope>>(StringComparer.Ordinal);

        /// <summary>The first instruction of every test: open its window.</summary>
        public static void Begin(object? self, string type, string method)
        {
            var scope = new Scope(Environment.CurrentManagedThreadId);
            Current.Value = scope;
            Hopped.Value = false;
            var name = (self?.GetType().FullName ?? type) + "." + method;
            Begun.GetOrAdd(name, _ => new ConcurrentQueue<Scope>()).Enqueue(scope);
        }

        /// <summary>The first instruction of every production method.</summary>
        public static void Ran()
        {
            var scope = Current.Value;
            if (scope == null || scope.Closed) return;
            scope.Ran = true;
            if (Open.Value == null) scope.Outside = true;
        }

        /// <summary>The first instruction of a declared entry point.</summary>
        public static void Enter(string entryPoint)
        {
            var outer = Open.Value;
            Open.Value = new Window(outer, entryPoint);
            // Only the outermost is an arrival (dev07-1-4-sr3): a door inside an open window is a room
            // the test was already in.
            if (outer != null) { Ran(); return; }
            var scope = Current.Value;
            if (scope == null || scope.Closed) return;
            scope.Ran = true;
            scope.Through(entryPoint);
            var own = !Hopped.Value &&
                      (Environment.CurrentManagedThreadId == scope.Thread || resumed == scope);
            if (own) scope.Entered(entryPoint);
            else scope.Elsewhere = true;
        }

        /// <summary>The first instruction of a woven async step: whose own flow, if anyone's, this
        /// thread now resumes.</summary>
        public static void Resume()
        {
            // Not a production fact: a test's own async steps resume too, and production steps are
            // woven to report `Ran` before this.
            if (resuming++ == 0) resumed = Hopped.Value ? null : Current.Value;
        }

        /// <summary>The <c>finally</c> of a woven async step.</summary>
        public static void Suspend()
        {
            if (resuming > 0 && --resuming == 0) resumed = null;
        }

        /// <summary>
        /// A hand-off, seen on the side that knows the window (dev07-1-4-sr2): the window is marked as
        /// having sent work, and the work is wrapped to carry it, wherever it runs.
        /// </summary>
        /// <remarks>
        /// Unchanged when no test's window is open, which is almost always: a process hands work off
        /// constantly and none of it is this run's business. The wrapper restores what it set on
        /// every way out, so a pool thread goes back to the pool as it came.
        /// </remarks>
        internal static Func<T> Carry<T>(Func<T> work)
        {
            var scope = Sent();
            return scope == null ? work : () => Within(scope, work);
        }

        internal static Action Carry(Action work)
        {
            var scope = Sent();
            return scope == null ? work : () => Within(scope, () => { work(); return true; });
        }

        internal static Action<T> Carry<T>(Action<T> work)
        {
            var scope = Sent();
            return scope == null ? work : argument => Within(scope, () => { work(argument); return true; });
        }

        internal static Func<TArgument, T> Carry<TArgument, T>(Func<TArgument, T> work)
        {
            var scope = Sent();
            return scope == null ? work : argument => Within(scope, () => work(argument));
        }

        /// <summary>The open window work is being sent from, marked as having sent it.</summary>
        private static Scope? Sent()
        {
            var scope = Current.Value;
            if (scope == null || scope.Closed) return null;
            scope.HandedOff = true;
            return scope;
        }

        private static T Within<T>(Scope scope, Func<T> work)
        {
            var (current, hopped) = (Current.Value, Hopped.Value);
            Current.Value = scope;
            Hopped.Value = true;
            try { return work(); }
            finally { Current.Value = current; Hopped.Value = hopped; }
        }

        /// <summary>The <c>finally</c> of a declared entry point, on every way out of it.</summary>
        public static void Exit()
        {
            var open = Open.Value;
            if (open != null) Open.Value = open.Outer;
        }

        /// <summary>
        /// The scope of the test VSTest just ended, closed so nothing after this counts for it.
        /// </summary>
        /// <remarks>
        /// Oldest first, because a theory's rows run one after another under the same name. A row
        /// whose body never ran began nothing, and takes the next row's scope if that row began
        /// before this one was reported: the error costs that row its fact (<c>not-checked</c>) and
        /// can grant nothing, because the row taking it was skipped.
        /// </remarks>
        internal static Scope? Take(string name)
        {
            if (!Begun.TryGetValue(name, out var queue) || !queue.TryDequeue(out var scope)) return null;
            scope.Closed = true;
            return scope;
        }

        internal sealed class Scope
        {
            public Scope(int thread) => Thread = thread;

            /// <summary>The thread the test's own code began on.</summary>
            public int Thread { get; }

            private volatile bool elsewhere, handedOff, outside;
            private readonly List<string> through = new List<string>();

            /// <summary>Production code ran with no window open (dev07-1-4-ur4).</summary>
            public bool Outside { get => outside; set => outside = value; }

            /// <summary>Every outermost entry point the test's work came in through, own or sent, in
            /// the order first entered (dev07-1-4-ur3).</summary>
            public void Through(string entryPoint)
            {
                lock (gate) if (!through.Contains(entryPoint)) through.Add(entryPoint);
            }

            public IReadOnlyList<string> EnteredThroughAll()
            {
                lock (gate) return through.ToArray();
            }

            /// <summary>An entry point reached by work the test sent elsewhere.</summary>
            public bool Elsewhere { get => elsewhere; set => elsewhere = value; }

            /// <summary>A hand-off seen inside the window, arrived or not.</summary>
            public bool HandedOff { get => handedOff; set => handedOff = value; }

            private readonly object gate = new object();
            private readonly List<string> entered = new List<string>();
            private volatile bool ran, closed;

            public bool Ran { get => ran; set => ran = value; }

            public bool Closed { get => closed; set => closed = value; }

            public void Entered(string entryPoint)
            {
                lock (gate) if (!entered.Contains(entryPoint)) entered.Add(entryPoint);
            }

            public IReadOnlyList<string> EnteredThrough()
            {
                lock (gate) return entered.ToArray();
            }
        }
    }
}
