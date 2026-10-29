using PlumbSpec;
using Xunit;

namespace Sample.Tests
{
    /// <summary>Stands in for an adopter's suite: some stories proven, one not built, one broken,
    /// one cited twice.</summary>
    public class SampleSpecTests
    {
        [Fact]
        [Proves("CM-101", "wiring", Ref = "JIRA-4412")]
        public void RoutesAnOrderToAQueue() => Assert.Equal(4, App.HandleRequest(2));

        [Fact]
        [Proves("CM-102", "unit")]
        [Proves("CM-103", "component")]
        public void OneTestCitingTwoStories() => Assert.Equal(5, "plumb".Length);

        // xUnit's skip is the "specified, not built" signal — pytest's skip in another spelling.
        [Fact(Skip = "UNPROVEN[CM-104] — no implementation yet")]
        [Proves("CM-104", "wiring")]
        public void NotBuiltYet() { }

        [Fact]
        [Proves("CM-105", "smoke")]
        public void Regressed() => Assert.True(1 == 2, "a claimed-done story that broke");

        /// <summary>One row passes and one fails, so the two must stay two citations.</summary>
        [Theory]
        [InlineData(2, 4)]
        [InlineData(3, 7)]
        [Proves("CM-107", "unit")]
        public void DoublesEveryRow(int n, int doubled) => Assert.Equal(doubled, App.Work(n));
    }

    /// <summary>A citation on the class is a citation on every test it holds.</summary>
    [Proves("CM-106", "unit")]
    public class ClassCitedTests
    {
        [Fact]
        public void First() => Assert.True(true);

        [Fact]
        public void Second() => Assert.True(true);
    }

    /// <summary>A test that cites nothing — counted as observed, and on no story.</summary>
    public class UncitedTests
    {
        [Fact]
        public void CitesNothingAndTouchesNothing() => Assert.Equal(4, 2 + 2);
    }
}
