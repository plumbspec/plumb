using System.Threading;
using System.Threading.Tasks;
using PlumbSpec;
using Xunit;

namespace Sample.Tests
{
    /// <summary>
    /// Every way a test's work can leave it, and the fact each reads (dev07-1-4-ur1.5). Work handed to
    /// another thread that reaches an entry point is `dispatched`, as on the JVM; work the test awaits
    /// stays the test's own, because .NET carries the test's flow across an await (dev07-1-3-sr05).
    /// </summary>
    public class HandOffTests
    {
        [Fact]
        [Proves("APP-2", "wiring")]
        public async Task HandsTheEntryPointToThePool() =>
            Assert.Equal(4, await Task.Run(() => App.HandleRequest(2)));

        [Fact]
        [Proves("DIS-1", "wiring")]
        public void StartsAThreadThatDrivesTheEntryPoint()
        {
            var answer = 0;
            var thread = new Thread(() => answer = App.HandleRequest(2));
            thread.Start();
            thread.Join();
            Assert.Equal(4, answer);
        }

        [Fact]
        [Proves("DIS-2", "wiring")]
        public void QueuesTheEntryPointToThePool()
        {
            using var done = new ManualResetEventSlim();
            var answer = 0;
            ThreadPool.QueueUserWorkItem(_ => { answer = App.HandleRequest(3); done.Set(); });
            done.Wait();
            Assert.Equal(6, answer);
        }

        /// <summary>The hand-off is seen and the work reaches nothing: still `dispatched`, because
        /// what left is what the fact is about, not what it did after.</summary>
        [Fact]
        [Proves("DIS-3", "unit")]
        public async Task HandsOffWorkThatReachesNothing() => Assert.Equal(1, await Task.Run(() => 1));

        /// <summary>An async hand-off: the entry point is reached after an await inside the handed-off
        /// work, on whichever thread resumes it — still the hand-off's, not the test's.</summary>
        [Fact]
        [Proves("DIS-4", "wiring")]
        public async Task HandsOffAsyncWorkThatDrivesTheEntryPointAfterAnAwait() =>
            Assert.Equal(2, await Task.Run(async () =>
            {
                await Task.Yield();
                return App.HandleRequest(1);
            }));

        [Fact]
        [Proves("DIS-5", "wiring")]
        public void StartsWorkFromTheFactory() =>
            Assert.Equal(8, Task.Factory.StartNew(() => App.HandleRequest(4)).Result);

        /// <summary>A hand-off the weave cannot see — a timer, made by the runtime's own library — still
        /// reads `dispatched` when its work arrives, because nothing proves it is the test's own flow
        /// (dev07-1-4-sr4).</summary>
        [Fact]
        [Proves("DIS-6", "wiring")]
        public void ATimerTheWeaveCannotSeeDrivesTheEntryPoint()
        {
            using var done = new ManualResetEventSlim();
            using var timer = new Timer(_ => { App.HandleRequest(1); done.Set(); }, null, 0, Timeout.Infinite);
            done.Wait();
        }

        /// <summary>Production hands the work off, not the test.</summary>
        [Fact]
        [Proves("APP-8", "wiring")]
        public void CallsProductionThatHandsTheEntryPointOff() => Assert.Equal(10, App.Dispatch(5));

        /// <summary>Awaited, the test resumes on another thread, and it is still the test.</summary>
        [Fact]
        [Proves("OWN-1", "wiring")]
        public async Task AwaitsThenDrivesTheEntryPoint()
        {
            await Task.Delay(20).ConfigureAwait(false);
            Assert.Equal(2, App.HandleRequest(1));
        }
    }
}
