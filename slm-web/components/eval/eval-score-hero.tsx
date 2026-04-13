import { cn } from "@/lib/utils"

interface EvalScoreHeroProps {
  score: number
  passed: number
  total: number
  className?: string
}

export function EvalScoreHero({ score, passed, total, className }: EvalScoreHeroProps) {
  const percentage = Math.round(score * 100 * 10) / 10

  return (
    <div className={cn("flex flex-col items-center gap-2 py-8", className)}>
      <div
        className={cn(
          "text-6xl font-bold tabular-nums tracking-tighter",
          score > 0.8
            ? "text-green-500"
            : score < 0.5
              ? "text-red-500"
              : undefined,
        )}
      >
        {percentage}%
      </div>
      <p className="text-muted-foreground">
        {passed} of {total} tasks passed
      </p>
    </div>
  )
}
