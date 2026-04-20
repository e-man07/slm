import { PageLayout } from "@/components/shared/page-layout"
import { EvalScoreHero } from "@/components/eval/eval-score-hero"
import { EvalCategoryChart } from "@/components/eval/eval-category-chart"
import { EvalTaskTable } from "@/components/eval/eval-task-table"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import evalData from "@/data/eval-results.json"

export default function EvalPage() {
  const { overall, categories, task_results } = evalData

  // Transform categories object to array
  const categoryArray = Object.entries(categories).map(([name, data]) => ({
    name,
    passed: (data as { passed: number }).passed,
    total: (data as { total: number }).total,
    score: (data as { score: number }).score,
  }))

  // Sort: highest score first, adversarial last
  categoryArray.sort((a, b) => {
    if (a.name === "adversarial") return 1
    if (b.name === "adversarial") return -1
    return b.score - a.score
  })

  return (
    <PageLayout>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold">Evaluation Dashboard</h1>
          <p className="mt-1 text-muted-foreground">
            80-task Solana/Anchor benchmark across 7 categories
          </p>
        </div>

        <EvalScoreHero
          score={overall.score}
          passed={overall.passed}
          total={overall.total}
        />

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Category Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <EvalCategoryChart categories={categoryArray} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Model Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Base Model</span>
                <span>Qwen2.5-Coder-7B-Instruct</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Training</span>
                <span>SFT on 10K curated records</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Architecture</span>
                <Badge variant="outline">7B dense</Badge>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">LoRA Rank</span>
                <span>16</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Eval Date</span>
                <span>{new Date(evalData.timestamp).toLocaleDateString()}</span>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Individual Task Results</CardTitle>
          </CardHeader>
          <CardContent>
            <EvalTaskTable tasks={task_results} />
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
