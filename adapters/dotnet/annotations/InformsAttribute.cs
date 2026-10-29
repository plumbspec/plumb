using System;

namespace PlumbSpec
{
    /// <summary>
    /// The citation for a subject that is never <em>done</em> — a decision, or a parameter.
    /// </summary>
    /// <remarks>
    /// A decision can only be informed, never proven, so <see cref="ProvesAttribute"/> is the wrong
    /// verb for it. There is no depth: a rung nothing could refute would be a claim nothing could
    /// lose.
    /// <code>
    /// [Fact]
    /// [Informs("D27", About = "falsifier")]
    /// public void NoFreeInputLevelCostsMoneyToServe() { ... }
    /// </code>
    /// </remarks>
    [AttributeUsage(AttributeTargets.Method | AttributeTargets.Class, AllowMultiple = true)]
    public sealed class InformsAttribute : Attribute
    {
        /// <param name="id">The decision or parameter this test informs.</param>
        public InformsAttribute(string id)
        {
            Id = id;
        }

        /// <summary>The decision or parameter this test informs.</summary>
        public string Id { get; }

        /// <summary>Which of the subject's aspects this evidence bears on.</summary>
        public string? About { get; set; }

        /// <summary>The consumer's own external key, carried through untouched.</summary>
        public string? Ref { get; set; }
    }
}
