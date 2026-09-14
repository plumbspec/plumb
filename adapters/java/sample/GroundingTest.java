import org.junit.jupiter.api.Test;
import org.plumbspec.Proves;

/** Three tests, three different truths about how they reached the system. */
class GroundingTest {

    @Test
    @Proves(value = "APP-1", depth = "wiring")
    void drivesTheEntryPointDirectly() throws Exception {
        assert App.handleRequest(2) == 4;
    }

    @Test
    @Proves(value = "APP-2", depth = "wiring")
    void handsTheEntryPointToAPoolThatAlreadyExisted() throws Exception {
        // The case a thread-local flag cannot survive, and the reason this is observed from
        // outside the process rather than propagated inside it.
        assert App.POOL.submit(() -> App.handleRequest(2)).get() == 4;
    }

    @Test
    @Proves(value = "APP-5", depth = "wiring")
    void drivesTheEntryPointWithoutCheckingIt() throws Exception {
        // Grounds exactly as APP-1 does and would not notice the answer changing. Grounding
        // cannot tell the two apart; mutation is the only thing here that can.
        App.handleRequest(2);
    }

    @Test
    void closesTheWindowWhenTheEntryPointThrows() {
        // Cites nothing on purpose: what it demonstrates is a property of the instrument, not of a
        // story, and a citation here would put the instrument's own behaviour on the board.
        //
        // Drives an entry point that throws, then — in the same test, on the same thread — drives
        // production code that no entry point reaches. If the window closed on the exception path,
        // `orphan` is outside it and chapter 4 will not scope a mutant to it. If it did not, the
        // window is still open, `orphan` is recorded as though the entry point had reached it, and
        // every later call on this thread joins it.
        try {
            App.failingRequest(2);
            assert false : "the entry point was supposed to throw";
        } catch (IllegalStateException expected) {
            // The path being tested.
        }
        assert App.orphan(2) == 3;
    }

    @Test
    @Proves(value = "APP-3", depth = "unit")
    void exercisesCodeNoEntryPointReaches() {
        assert App.orphan(2) == 3;
    }
}
