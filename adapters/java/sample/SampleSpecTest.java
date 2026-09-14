import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.plumbspec.Proves;

/** Stands in for an adopter's suite: some stories proven, one abandoned, one cited twice. */
class SampleSpecTest {

    @Test
    @Proves(value = "CM-101", depth = "wiring", ref = "JIRA-4412")
    void routesAnOrderToAQueue() {
        assert 2 + 2 == 4;
    }

    @Test
    @Proves(value = "CM-102", depth = "unit")
    @Proves(value = "CM-103", depth = "component")
    void oneTestCitingTwoStories() {
        assert "plumb".length() == 5;
    }

    @Test
    @Proves(value = "CM-104", depth = "wiring")
    void notBuiltYet() {
        // JUnit's abort is the "specified, not built" signal — pytest's skip in another spelling.
        Assumptions.abort("UNPROVEN[CM-104] — no implementation yet");
    }

    @Test
    @Proves(value = "CM-105", depth = "smoke")
    void regressed() {
        assert 1 == 2 : "a claimed-done story that broke";
    }
}
