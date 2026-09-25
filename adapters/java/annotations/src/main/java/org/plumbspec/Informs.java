package org.plumbspec;

import java.lang.annotation.*;

/**
 * The citation for a subject that is never <em>done</em> — a decision, or a parameter.
 *
 * <p>A decision is a claim about the <em>future</em>: this choice will keep being the right one. A
 * parameter is a decision with a model and a measurement. Neither can be <em>proven</em>, only
 * informed — repeatedly, by evidence that keeps arriving — so {@link Proves} is the wrong verb for
 * them, and reusing it would import a doneness reading into the one place that must not carry one.
 *
 * <p>Separate from {@code @Proves} rather than a member of it, because a reader scanning a test
 * file learns the thing they act on from the tag alone: <em>that is not my code's test</em>.
 *
 * <pre>
 * &#64;Test
 * &#64;Informs(value = "D27", about = "falsifier")
 * void noFreeInputLevelCostsMoneyToServe() { ... }
 * </pre>
 *
 * <p><strong>There is no depth.</strong> A depth is a rung the run refutes — a test claiming
 * {@code wiring} whose execution never reached wired code is caught lying. The analogue for a
 * decision would be authored and uncheckable, so it would be a number nothing could contradict.
 * Its absence is the claim.
 *
 * <p>Plumb reports that something informed an aspect. It does not report whether your falsifier is
 * a good one, whether your control was sound, or which of two settings is better — those are yours
 * to judge, and a tool that graded them would be selling the one thing it cannot deliver.
 *
 * @see <a href="https://plumbspec.org">plumbspec.org</a>
 */
@Repeatable(Informs.Citations.class)
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.METHOD, ElementType.TYPE})
public @interface Informs {

    /**
     * The subject this test informs — a decision or a parameter.
     *
     * <p>Opaque to Plumb, exactly as a story id is: whatever your organisation already uses.
     *
     * @return the subject identifier, in the citing project's own vocabulary
     */
    String value();

    /**
     * Which of the subject's aspects this citation bears on.
     *
     * <p>A decision has three — that its levers were measured, that its outcome occurred, and that
     * the condition which would make it wrong has not fired. They close at different times for
     * different reasons, so one word for all three loses the finding.
     *
     * <p>Empty where the subject has only one aspect. The name is checked against what the subject
     * declares and is never interpreted: it routes evidence, and asserts nothing.
     *
     * @return the aspect this citation is about, or empty where there is only one
     */
    String about() default "";

    /**
     * Your own external key, carried and never parsed.
     *
     * @return the citing project's identifier for this, or empty
     */
    String ref() default "";

    /** Container for the repeatable form. */
    @Retention(RetentionPolicy.RUNTIME)
    @Target({ElementType.METHOD, ElementType.TYPE})
    @interface Citations {
        Informs[] value();
    }
}
