using System;
using System.Threading.Tasks;
using PlumbSpec;
using Xunit;

namespace Sample.Tests
{
    /// <summary>
    /// The window: from entering an entry point until leaving the outermost one, kept per logical
    /// flow (dev07-1-3-sr05) — so an async entry point's window lasts until its work does, not until
    /// its first await returns control to the caller.
    /// </summary>
    public class WindowTests
    {
        [Fact]
        [Proves("ASY-1", "wiring")]
        public async Task AwaitsAnAsyncEntryPoint() => Assert.Equal(4, await App.HandleAsync(2));

        [Fact]
        [Proves("ASY-2", "wiring")]
        public void WaitsOnAnAsyncEntryPoint() => Assert.Equal(6, App.HandleAsync(3).Result);

        /// <summary>An async test that runs nothing of production: its own steps are not production.</summary>
        [Fact]
        [Proves("ASY-3", "unit")]
        public async Task AwaitsAndTouchesNothing()
        {
            await Task.Yield();
            Assert.True(true);
        }

        /// <summary>The entry point throws; what the test runs afterwards is outside its window.</summary>
        [Fact]
        [Proves("WIN-1", "wiring")]
        public void RunsProductionAfterAnEntryPointThrew()
        {
            Assert.Throws<ArgumentException>(() => App.FailingRequest(1));
            Assert.Equal(4, App.Work(2));
        }
    }
}
