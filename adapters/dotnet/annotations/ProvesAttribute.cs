using System;

namespace PlumbSpec
{
    /// <summary>
    /// The one authored link, on the test — .NET's spelling of pytest's <c>proves</c> marker and
    /// Java's <c>@Proves</c>.
    /// </summary>
    /// <remarks>
    /// A story is proven when a test citing it passed <em>and</em> that test's execution reached
    /// wired production code. Put it on the test, never on the production code: the thing being
    /// judged does not get to claim it passed. Repeatable, because a citation is per (test, story)
    /// pair; on a class, it cites for every test the class holds.
    /// <code>
    /// [Fact]
    /// [Proves("APP-142", "wiring")]
    /// public void OrdersAreRouted() { ... }
    /// </code>
    /// Whatever framework runs the test — xUnit, NUnit or MSTest — this is read the same way.
    /// </remarks>
    [AttributeUsage(AttributeTargets.Method | AttributeTargets.Class, AllowMultiple = true)]
    public sealed class ProvesAttribute : Attribute
    {
        /// <param name="id">The story, in the citing project's own vocabulary. Opaque to plumb.</param>
        /// <param name="depth">How deep the test reached — <c>unit</c>, <c>component</c>,
        /// <c>wiring</c>, <c>standards-integration</c> or <c>smoke</c>. A claim the run either
        /// supports or refutes.</param>
        public ProvesAttribute(string id, string depth)
        {
            Id = id;
            Depth = depth;
        }

        /// <summary>The story this test claims to prove.</summary>
        public string Id { get; }

        /// <summary>How deep this test claims to reach.</summary>
        public string Depth { get; }

        /// <summary>The consumer's own external key, carried through untouched.</summary>
        public string? Ref { get; set; }
    }
}
