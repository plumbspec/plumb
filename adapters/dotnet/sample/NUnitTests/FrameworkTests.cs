using NUnit.Framework;
using PlumbSpec;

namespace Sample.NUnit
{
    /// <summary>Each of NUnit's own spellings of a result, cited once.</summary>
    public class FrameworkTests
    {
        [Test, Proves("FW-1", "unit")]
        public void Passes() => Assert.Pass();

        [Test, Ignore("UNPROVEN[FW-2]"), Proves("FW-2", "unit")]
        public void Ignored() { }

        [Test, Proves("FW-3", "unit")]
        public void Inconclusive() => Assert.Inconclusive("UNPROVEN[FW-3]");

        [TestCase(1), TestCase(2), Proves("FW-4", "unit")]
        public void Rows(int n) => Assert.That(n, Is.EqualTo(1));

        [Test, Proves("FW-5", "unit")]
        public void Fails() => Assert.Fail("a claimed-done story that broke");
    }
}
