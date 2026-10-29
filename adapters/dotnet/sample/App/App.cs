using System;
using System.Collections.Generic;

namespace Sample
{
    /// <summary>Stands in for an adopter's production code. The entry points are declared in
    /// <c>plumb.toml</c>; everything else is reachable from them or from nowhere.</summary>
    public static class App
    {
        /// <summary>The wired surface — where the real system begins (dev07-1-3).</summary>
        public static int HandleRequest(int n) => Work(n);

        /// <summary>Reachable only through the entry point, unless a test calls it directly.</summary>
        public static int Work(int n) => n * 2;

        /// <summary>
        /// An entry point shaped to break a careless weave: several returns, short branches a
        /// longer body pushes out of range, a switch, a loop, and handlers of every kind. Wrapping
        /// it moves every instruction, so a branch or a handler left pointing at the old offset is
        /// a wrong answer or an invalid program.
        /// </summary>
        public static int Shapes(int n)
        {
            if (n < 0) return -1;
            var total = 0;
            for (var i = 0; i < n; i++) total += i;
            switch (n)
            {
                case 0: return 100;
                case 1: total += 10; break;
                case 2: total += 20; break;
                case 3: total += 30; break;
            }
            try
            {
                if (n == 4) throw new InvalidOperationException("four");
                total += Work(n);
            }
            catch (InvalidOperationException) when (n == 4)
            {
                total = 400;
            }
            finally
            {
                total += 1;
            }
            return total;
        }

        /// <summary>A generic entry point, so the result the wrap holds is typed by the caller.</summary>
        public static List<T> Echo<T>(T value) => new List<T> { value };

        /// <summary>An entry point that returns nothing.</summary>
        public static void Record(List<int> into) => into.Add(Work(1));

        /// <summary>An entry point that throws, so the window must close on the way out.</summary>
        public static int FailingRequest(int n) => throw new ArgumentException("refused " + n);
    }
}
