import org.junit.jupiter.api.Test;

/**
 * A test that cites nothing — the case the observer must decline to answer for (`dev07-1-4`).
 *
 * Grounding is recorded against a citation, so this test has no entry in the manifest and the
 * observer does not watch the production surface while it runs. `inert` is the <em>positive</em>
 * claim that no production code ran anywhere; making it here would be asserting the one thing
 * nothing looked for. The honest answer is the weaker `ungrounded`.
 *
 * It exists because the sample was otherwise cited end to end, which made that invariant
 * impossible to check: every test was watched, so no test could expose an observer that answered
 * for one it had not watched.
 */
class UncitedTest {

    @Test
    void citesNothingAndTouchesNothing() {
        assert 2 + 2 == 4;
    }
}
