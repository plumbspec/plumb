using Microsoft.VisualStudio.TestTools.UnitTesting;
using PlumbSpec;

namespace Sample.MSTest
{
    /// <summary>Each of MSTest's own spellings of a result, cited once.</summary>
    [TestClass]
    public class FrameworkTests
    {
        [TestMethod, Proves("FW-1", "unit")]
        public void Passes() { }

        [TestMethod, Ignore, Proves("FW-2", "unit")]
        public void Ignored() { }

        [TestMethod, Proves("FW-3", "unit")]
        public void Inconclusive() => Assert.Inconclusive("UNPROVEN[FW-3]");

        [DataTestMethod, DataRow(1), DataRow(2), Proves("FW-4", "unit")]
        public void Rows(int n) => Assert.AreEqual(1, n);

        [TestMethod, Proves("FW-5", "unit")]
        public void Fails() => Assert.Fail("a claimed-done story that broke");
    }
}
