import { cn } from "@/lib/utils"

interface CategoryData {
  name: string
  passed: number
  total: number
  score: number
}

interface EvalCategoryChartProps {
  categories: CategoryData[]
  className?: string
}

const CATEGORY_LABELS: Record<string, string> = {
  pda_derivation: "PDA Derivation",
  anchor_constraints: "Anchor Constraints",
  spl_token_ops: "SPL Token Ops",
  cpi_patterns: "CPI Patterns",
  error_handling: "Error Handling",
  adversarial: "Adversarial",
  transaction_construction: "Tx Construction",
}

export function EvalCategoryChart({ categories, className }: EvalCategoryChartProps) {
  return (
    <div className={cn("space-y-3", className)}>
      {categories.map((cat) => {
        const percentage = Math.round(cat.score * 100)
        const label = CATEGORY_LABELS[cat.name] ?? cat.name

        return (
          <div key={cat.name} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span>{label}</span>
              <span className="tabular-nums text-muted-foreground">
                {cat.passed}/{cat.total} ({percentage}%)
              </span>
            </div>
            <div className="h-2 w-full bg-muted">
              <div
                className={cn(
                  "h-full transition-all duration-500",
                  percentage === 100
                    ? "bg-chart-1"
                    : percentage >= 80
                      ? "bg-chart-2"
                      : percentage >= 50
                        ? "bg-chart-4"
                        : "bg-destructive",
                )}
                style={{ width: `${percentage}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
