/**
 * Fix 9: Eval score hero - pass/fail color
 * Add green color when score > 0.8 in components/eval/eval-score-hero.tsx
 *
 * RED  - test expects green styling when score > 0.8, but current source has no color logic
 * GREEN - add conditional color class
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { EvalScoreHero } from "@/components/eval/eval-score-hero"

vi.mock("@/lib/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}))

describe("Fix 9 - Eval score hero pass/fail color", () => {
  it("applies green color class when score > 0.8", () => {
    render(<EvalScoreHero score={0.875} passed={70} total={80} />)
    const scoreEl = screen.getByText("87.5%")
    // Check that the score element has a green-related class
    expect(scoreEl.className).toMatch(/green/)
  })

  it("does NOT apply green color class when score <= 0.8", () => {
    render(<EvalScoreHero score={0.6} passed={48} total={80} />)
    const scoreEl = screen.getByText("60%")
    expect(scoreEl.className).not.toMatch(/green/)
  })

  it("applies red/destructive color when score < 0.5", () => {
    render(<EvalScoreHero score={0.3} passed={24} total={80} />)
    const scoreEl = screen.getByText("30%")
    expect(scoreEl.className).toMatch(/red|destructive/)
  })
})
