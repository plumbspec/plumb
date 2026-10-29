namespace Sample
{
    /// <summary>Stands in for an adopter's production code. <c>HandleRequest</c> is the declared
    /// entry point.</summary>
    public static class App
    {
        /// <summary>The wired surface — where the real system begins (dev07-1-3).</summary>
        public static int HandleRequest(int n) => Work(n);

        /// <summary>Reachable only through the entry point.</summary>
        public static int Work(int n) => n * 2;
    }
}
