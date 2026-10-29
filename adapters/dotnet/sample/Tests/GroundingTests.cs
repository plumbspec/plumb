using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using PlumbSpec;
using Xunit;

namespace Sample.Tests
{
    /// <summary>One test of each shape the adapters are asked about alike
    /// (tests/test_adapter_conformance.py).</summary>
    public class GroundingTests
    {
        [Fact]
        [Proves("APP-1", "wiring")]
        public void DrivesTheEntryPointDirectly() => Assert.Equal(6, App.HandleRequest(3));

        [Fact]
        [Proves("APP-3", "unit")]
        public void ExercisesCodeNoEntryPointReaches() => Assert.Equal(4, App.Work(2));

        /// <summary>Reads the artifact and runs none of it — `inert`, once a read is observable
        /// (dev07-1-3-u07).</summary>
        [Fact]
        [Proves("APP-4", "unit")]
        public void TheEntryPointTypeIsWhereWeSayItIs()
        {
            var bytes = File.ReadAllBytes(Path.Combine(AppContext.BaseDirectory, "App.dll"));
            Assert.True(bytes.Length > 0);
        }

        /// <summary>Every answer the woven entry point gives must be the one it gave unwoven.</summary>
        [Fact]
        [Proves("APP-6", "wiring")]
        public void AnEntryPointOfEveryShapeStillAnswersAsBuilt()
        {
            Assert.Equal(-1, App.Shapes(-5));
            Assert.Equal(100, App.Shapes(0));
            Assert.Equal(13, App.Shapes(1));
            Assert.Equal(26, App.Shapes(2));
            Assert.Equal(40, App.Shapes(3));
            Assert.Equal(401, App.Shapes(4));
            Assert.Equal(21, App.Shapes(5));
            Assert.Equal(new List<string> { "x" }, App.Echo("x"));
            Assert.Equal(new List<int> { 7 }, App.Echo(7));
            var into = new List<int>();
            App.Record(into);
            Assert.Equal(new List<int> { 2 }, into);
        }

        /// <summary>The entry point throws, and the window must not stay open behind it.</summary>
        [Fact]
        [Proves("APP-7", "wiring")]
        public void AnEntryPointThatThrowsStillGrounds() =>
            Assert.Throws<ArgumentException>(() => App.FailingRequest(1));
    }

    /// <summary>
    /// Two tests xUnit runs at once, because their classes are separate collections: one inside an
    /// entry point while the other waits beside it, touching nothing. One flag shared by the process
    /// would hand the waiting test the other's grounding.
    /// </summary>
    public static class Together
    {
        public static readonly Barrier Meet = new Barrier(2);
    }

    public class DrivingAlongside
    {
        [Fact]
        [Proves("PAR-1", "wiring")]
        public void DrivesTheEntryPointWhileAnotherTestWaits()
        {
            Together.Meet.SignalAndWait(TimeSpan.FromSeconds(5));
            Assert.Equal(2, App.HandleRequest(1));
            Together.Meet.SignalAndWait(TimeSpan.FromSeconds(5));
        }
    }

    public class WaitingAlongside
    {
        [Fact]
        [Proves("PAR-2", "unit")]
        public void TouchesNothingWhileAnotherTestDrives()
        {
            Together.Meet.SignalAndWait(TimeSpan.FromSeconds(5));
            Together.Meet.SignalAndWait(TimeSpan.FromSeconds(5));
            Assert.True(true);
        }
    }
}
