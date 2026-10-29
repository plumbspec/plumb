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

        /// <summary>How deep this thread is inside entry points. Per thread, so an entry point is the
        /// outermost on the thread it is entered on (dev07-1-4-sr3).</summary>
        [ThreadStatic] private static int depth;

        private static readonly ConcurrentDictionary<string, ConcurrentQueue<Scope>> Begun =
            new ConcurrentDictionary<string, ConcurrentQueue<Scope>>(StringComparer.Ordinal);

        /// <summary>The first instruction of every test: open its window.</summary>
        public static void Begin(object? self, string type, string method)
        {
            var scope = new Scope();
            Current.Value = scope;
            var name = (self?.GetType().FullName ?? type) + "." + method;
            Begun.GetOrAdd(name, _ => new ConcurrentQueue<Scope>()).Enqueue(scope);
        }

        /// <summary>The first instruction of every production method.</summary>
        public static void Ran()
        {
            var scope = Current.Value;
            if (scope != null && !scope.Closed) scope.Ran = true;
        }

        /// <summary>The first instruction of a declared entry point.</summary>
        public static void Enter(string entryPoint)
        {
            if (depth++ != 0) { Ran(); return; }
            var scope = Current.Value;
            if (scope == null || scope.Closed) return;
            scope.Ran = true;
            scope.Entered(entryPoint);
        }

        /// <summary>The <c>finally</c> of a declared entry point, on every way out of it.</summary>
        public static void Exit()
        {
            if (depth > 0) depth--;
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
