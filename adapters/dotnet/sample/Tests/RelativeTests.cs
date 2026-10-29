using System;
using System.IO;
using PlumbSpec;
using Xunit;

namespace Sample.Tests
{
    /// <summary>
    /// Tests that reach their project's files the way real suites do: up from the output directory,
    /// or up from the working directory VSTest gives them. Plumb runs a copy of the output, outside
    /// the project's tree, and these must find what they find under `dotnet test` (dev07-1-3-sr14).
    /// </summary>
    public class RelativeTests
    {
        [Fact]
        [Proves("REL-1", "unit")]
        public void ReadsAFileUpFromTheOutputDirectory() =>
            Assert.Equal("beside the project", File.ReadAllText(
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "Data.txt")).Trim());

        [Fact]
        [Proves("REL-2", "unit")]
        public void ReadsAFileUpFromTheWorkingDirectory() =>
            Assert.Equal("beside the project", File.ReadAllText("../../../Data.txt").Trim());
    }
}
