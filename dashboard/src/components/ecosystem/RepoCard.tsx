import { Link } from 'react-router-dom';
import { Star, GitBranch, Calendar, Tag, AlertCircle, Archive } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { EcosystemRepoProfile } from '@/api/ecosystem';
import { CATEGORY_LABELS } from '@/api/ecosystem';

interface RepoCardProps {
  /** 仓档案数据 */
  repo: EcosystemRepoProfile;
}

/**
 * 格式化星标数：1234 -> 1.2k，12345 -> 12.3k，1234567 -> 1.2M
 */
function formatStars(stars: number): string {
  if (stars >= 1_000_000) return `${(stars / 1_000_000).toFixed(1)}M`;
  if (stars >= 1_000) return `${(stars / 1_000).toFixed(1)}k`;
  return String(stars);
}

/**
 * 计算距今天数 — 用于 last_commit_at 显示。
 */
function daysSince(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  return Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24));
}

/**
 * 类别色彩映射 — 不同类别用不同色调便于扫读。
 */
function categoryColor(category: string | null): string {
  switch (category) {
    case 'agent-framework':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300';
    case 'mcp-server':
      return 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300';
    case 'memory-system':
      return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
    case 'skill-system':
      return 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300';
    case 'tooling':
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
    default:
      return 'bg-muted text-muted-foreground';
  }
}

/**
 * 单仓卡片 — 列表视图的基本单元。点击跳详情页。
 */
export function RepoCard({ repo }: RepoCardProps) {
  const lastCommitDays = daysSince(repo.last_commit_at);
  const isStale = lastCommitDays !== null && lastCommitDays > 180;
  const summary = repo.one_line_summary || repo.description_excerpt || repo.description || '暂无描述';

  return (
    <Link
      to={`/ecosystem/${repo.id}`}
      className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg"
      aria-label={`查看 ${repo.repo_full_name} 详情`}
    >
      <Card className="h-full transition-colors hover:border-primary/50 hover:bg-accent/30">
        <CardContent className="p-4 space-y-2.5">
          {/* 头部：仓名 + star */}
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h3 className="font-semibold text-sm leading-snug truncate">
                {repo.repo_full_name}
              </h3>
              {repo.language && (
                <p className="text-xs text-muted-foreground mt-0.5">{repo.language}</p>
              )}
            </div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
              <Star className="h-3.5 w-3.5 text-yellow-500" aria-hidden="true" />
              <span className="font-medium">{formatStars(repo.stars)}</span>
            </div>
          </div>

          {/* 一句话摘要 */}
          <p className="text-xs text-muted-foreground line-clamp-2 min-h-[2rem]">
            {summary}
          </p>

          {/* 标签条：category + topics + 状态 */}
          <div className="flex flex-wrap items-center gap-1">
            {repo.relevance_category && (
              <span
                className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium ${categoryColor(repo.relevance_category)}`}
              >
                <Tag className="h-2.5 w-2.5" aria-hidden="true" />
                {CATEGORY_LABELS[repo.relevance_category] ?? repo.relevance_category}
              </span>
            )}
            {repo.topics?.slice(0, 3).map((topic) => (
              <Badge key={topic} variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                {topic}
              </Badge>
            ))}
            {repo.topics && repo.topics.length > 3 && (
              <span className="text-[10px] text-muted-foreground">
                +{repo.topics.length - 3}
              </span>
            )}
          </div>

          {/* 底部状态条 */}
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground pt-1 border-t">
            {lastCommitDays !== null && (
              <span className="flex items-center gap-1">
                <GitBranch className="h-3 w-3" aria-hidden="true" />
                {lastCommitDays === 0 ? '今天' : `${lastCommitDays} 天前`}
              </span>
            )}
            {repo.is_archived && (
              <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                <Archive className="h-3 w-3" aria-hidden="true" />
                已归档
              </span>
            )}
            {isStale && !repo.is_archived && (
              <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                <Calendar className="h-3 w-3" aria-hidden="true" />
                沉寂
              </span>
            )}
            {repo.needs_deep_review && (
              <span className="ml-auto flex items-center gap-1 text-blue-600 dark:text-blue-400">
                <AlertCircle className="h-3 w-3" aria-hidden="true" />
                待深扫
              </span>
            )}
            {repo.relevance_score > 0 && !repo.needs_deep_review && (
              <span className="ml-auto">相关性 {repo.relevance_score}/10</span>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
