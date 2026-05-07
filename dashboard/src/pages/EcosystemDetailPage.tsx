import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Star,
  ExternalLink,
  GitBranch,
  Calendar,
  Tag,
  AlertCircle,
  Archive,
  Clock,
  Code2,
  Info,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useEcosystemRepoDetail,
  useEcosystemRepoFull,
  CATEGORY_LABELS,
  DEEP_REVIEW_STATUS_LABELS,
  INTEGRATION_RECOMMENDATION_LABELS,
} from '@/api/ecosystem';
import { CapabilityTags } from '@/components/ecosystem/CapabilityTags';
import { DeepReviewSection } from '@/components/ecosystem/DeepReviewSection';
import { RelationsSection } from '@/components/ecosystem/RelationsSection';
import { ScanRunSection } from '@/components/ecosystem/ScanRunSection';

/**
 * 单仓详情页 — 展示完整档案、元数据、深扫摘要（v2 待落地）。
 * 路径：/ecosystem/:repoId
 */
export function EcosystemDetailPage() {
  const { repoId } = useParams<{ repoId: string }>();
  // v2 全息详情：主数据源（包含 profile + tags + deep_reviews + relations + scan_run）
  const { data: full, isLoading: isFullLoading } = useEcosystemRepoFull(repoId ?? null);
  // v1 列表查找：fallback profile 信息（v2 失败时使用）
  const {
    data: fallbackRepo,
    isLoading: isFallbackLoading,
    error: fallbackError,
  } = useEcosystemRepoDetail(repoId ?? null);

  // 合并：v2.profile 优先，否则 v1
  const repo = full?.profile ?? fallbackRepo;
  const isLoading = isFullLoading && isFallbackLoading;

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-32 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (!repo) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Link to="/ecosystem">
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="mr-1 h-4 w-4" aria-hidden="true" />
            返回列表
          </Button>
        </Link>
        <Card>
          <CardContent className="p-6 flex items-start gap-3 text-destructive">
            <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-medium">未找到该仓档案</p>
              <p className="text-sm text-muted-foreground mt-1">
                {fallbackError?.message ?? '请检查仓 ID 是否正确，或返回列表重新选择。'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const formatDate = (iso: string | null | undefined): string => {
    if (!iso) return '未知';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
  };

  const summary = repo.one_line_summary || repo.description_excerpt || repo.description || '暂无描述';

  // 提取最新一条深扫记录的状态 + 集成建议（用于头部徽章 + 详情页一目了然）
  const latestReview =
    full?.deep_reviews && full.deep_reviews.length > 0
      ? [...full.deep_reviews].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        )[0]
      : null;

  const reviewStatusStyle: Record<string, string> = {
    completed: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30',
    running: 'bg-blue-500/10 text-blue-600 border-blue-500/30',
    pending: 'bg-muted text-muted-foreground border-border',
    failed: 'bg-rose-500/10 text-rose-600 border-rose-500/30',
    skipped: 'bg-amber-500/10 text-amber-600 border-amber-500/30',
  };

  const recommendationStyle: Record<string, string> = {
    adopt: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40',
    experiment: 'bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/40',
    hold: 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40',
    avoid: 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/40',
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-4">
        {/* 顶栏：返回按钮 */}
        <div className="flex items-center gap-2">
          <Link to="/ecosystem">
            <Button variant="ghost" size="sm" aria-label="返回列表">
              <ArrowLeft className="mr-1 h-4 w-4" aria-hidden="true" />
              返回列表
            </Button>
          </Link>
        </div>

        {/* 头部卡片 */}
        <Card>
          <CardHeader>
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
              <div className="min-w-0 flex-1">
                <CardTitle className="text-2xl flex items-center gap-2 flex-wrap break-all">
                  {repo.repo_full_name}
                  {repo.is_archived && (
                    <Badge variant="outline" className="text-amber-600 border-amber-600">
                      <Archive className="mr-1 h-3 w-3" aria-hidden="true" />
                      已归档
                    </Badge>
                  )}
                  {repo.needs_deep_review && !latestReview && (
                    <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/30 hover:bg-blue-500/20">
                      待深扫
                    </Badge>
                  )}
                  {latestReview && (
                    <Badge
                      variant="outline"
                      className={`text-xs ${reviewStatusStyle[latestReview.status] ?? ''}`}
                    >
                      深扫:{DEEP_REVIEW_STATUS_LABELS[latestReview.status] ?? latestReview.status}
                    </Badge>
                  )}
                  {latestReview?.integration_recommendation && (
                    <Badge
                      variant="outline"
                      className={`text-xs font-medium ${recommendationStyle[latestReview.integration_recommendation] ?? ''}`}
                    >
                      建议:
                      {INTEGRATION_RECOMMENDATION_LABELS[latestReview.integration_recommendation] ??
                        latestReview.integration_recommendation}
                    </Badge>
                  )}
                </CardTitle>
                <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{summary}</p>
              </div>

              <div className="flex flex-col items-end gap-1.5 shrink-0">
                <div className="flex items-center gap-1.5 text-base font-semibold">
                  <Star className="h-4 w-4 text-yellow-500" aria-hidden="true" />
                  {repo.stars.toLocaleString()}
                </div>
                <a
                  href={`https://github.com/${repo.repo_full_name}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                >
                  GitHub
                  <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
                {repo.homepage && (
                  <a
                    href={repo.homepage}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                  >
                    主页
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </a>
                )}
              </div>
            </div>
          </CardHeader>
        </Card>

        {/* 元数据网格 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 基本信息 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Info className="h-4 w-4" aria-hidden="true" />
                基本信息
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <MetaRow label="拥有者" value={repo.owner} />
              <MetaRow label="主语言" value={repo.language ?? '未识别'} icon={<Code2 className="h-3.5 w-3.5" />} />
              <MetaRow
                label="类别"
                value={
                  repo.relevance_category
                    ? (CATEGORY_LABELS[repo.relevance_category] ?? repo.relevance_category)
                    : '未分类'
                }
                icon={<Tag className="h-3.5 w-3.5" />}
              />
              <MetaRow
                label="相关性评分"
                value={`${repo.relevance_score} / 10`}
              />
            </CardContent>
          </Card>

          {/* 时间轴 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Clock className="h-4 w-4" aria-hidden="true" />
                时间轴
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <MetaRow
                label="最后提交"
                value={formatDate(repo.last_commit_at)}
                icon={<GitBranch className="h-3.5 w-3.5" />}
              />
              {repo.pushed_at && (
                <MetaRow
                  label="最后 Push"
                  value={formatDate(repo.pushed_at)}
                  icon={<GitBranch className="h-3.5 w-3.5" />}
                />
              )}
              <MetaRow
                label="最后扫描"
                value={formatDate(repo.last_scanned_at)}
                icon={<Calendar className="h-3.5 w-3.5" />}
              />
              <MetaRow
                label="首次入档"
                value={formatDate(repo.first_seen_at)}
                icon={<Calendar className="h-3.5 w-3.5" />}
              />
            </CardContent>
          </Card>
        </div>

        {/* Topics */}
        {repo.topics && repo.topics.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Tag className="h-4 w-4" aria-hidden="true" />
                GitHub Topics ({repo.topics.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1.5">
                {repo.topics.map((topic) => (
                  <Badge key={topic} variant="secondary" className="text-xs">
                    {topic}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 完整描述 */}
        {repo.description && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">仓库描述</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">
                {repo.description}
              </p>
            </CardContent>
          </Card>
        )}

        {/* 深度档案区（v2 API: GET /api/ecosystem/profiles/{full_name:path}/full） */}
        <div className="pt-2">
          <h2 className="text-sm font-semibold text-muted-foreground tracking-wide uppercase mb-3">
            深度档案
          </h2>

          {isFullLoading && !full ? (
            <div className="space-y-3">
              <Skeleton className="h-32 w-full" />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Skeleton className="h-40" />
                <Skeleton className="h-40" />
              </div>
            </div>
          ) : !full ? (
            <Card className="border-dashed">
              <CardContent className="p-4">
                <div className="flex items-start gap-2 text-sm text-muted-foreground">
                  <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden="true" />
                  <div>
                    <p className="font-medium text-foreground">深度档案暂不可用</p>
                    <p className="mt-1 text-xs">
                      v2 API 调用失败 — 显示基础信息。该仓可能未深扫或服务暂不可达。
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {/* 能力标签 + 扫描记录 网格 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <CapabilityTags tags={full.tags} />
                <ScanRunSection scanRun={full.scan_run} />
              </div>

              {/* 深扫摘要 */}
              <DeepReviewSection reviews={full.deep_reviews} />

              {/* 关联仓 */}
              <RelationsSection
                outgoing={full.relations_from}
                incoming={full.relations_to}
                currentRepoFullName={full.profile.repo_full_name}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * 元数据行 — 标签 + 值的统一展示。
 */
function MetaRow({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 border-b border-border/40 last:border-0">
      <span className="text-muted-foreground text-xs flex items-center gap-1.5">
        {icon}
        {label}
      </span>
      <span className="font-medium text-right">{value}</span>
    </div>
  );
}
