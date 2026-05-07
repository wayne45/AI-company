import { useState, useMemo } from 'react';
import { AlertCircle, Boxes } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { useEcosystemProfiles } from '@/api/ecosystem';
import type { EcosystemFilters } from '@/api/ecosystem';
import { RepoCard } from '@/components/ecosystem/RepoCard';
import { FilterBar } from '@/components/ecosystem/FilterBar';
import { EcosystemStatsBar } from '@/components/ecosystem/EcosystemStatsBar';
import { useProject } from '@/context/ProjectContext';

/**
 * Ecosystem 列表页 — 浏览所有已扫的生态仓档案。
 * 路径：/ecosystem
 * 数据源：GET /api/ecosystem/profiles?facet_counts=true
 *
 * UX 增强：
 *   - 顶部 StatsBar：项目 chip + 总数 / 已深扫 / 待深扫 / 失活 / Top 3 类别
 *   - 后端按 X-Project-Id header 自动隔离，切换项目后 React Query invalidate 触发刷新
 */
export function EcosystemListPage() {
  const { projectId, projectName } = useProject();
  const [filters, setFilters] = useState<EcosystemFilters>({
    limit: 200,
    facetCounts: true,
  });

  const { data, isLoading, error } = useEcosystemProfiles(filters);
  const profiles = data?.profiles ?? [];

  // 客户端二次过滤：keyword 也匹配 owner/description
  // 后端的 keyword 已经匹配 name，这里补充对 description 的本地兜底过滤
  const filtered = useMemo(() => {
    if (!filters.keyword) return profiles;
    const q = filters.keyword.toLowerCase();
    return profiles.filter(
      (p) =>
        p.repo_full_name.toLowerCase().includes(q) ||
        p.owner.toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q) ||
        (p.description ?? '').toLowerCase().includes(q) ||
        (p.one_line_summary ?? '').toLowerCase().includes(q),
    );
  }, [profiles, filters.keyword]);

  return (
    <div className="flex h-full flex-col">
      {/* 页头 */}
      <div className="border-b px-6 py-4 bg-background">
        <div className="flex items-center gap-2">
          <Boxes className="h-5 w-5 text-primary" aria-hidden="true" />
          <h1 className="text-xl font-semibold">生态仓档案</h1>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Claude Agent / MCP / Memory / Skill 等开源仓的广索引视图。点击卡片进入详情。
          {projectName && (
            <>
              {' '}当前已按项目 <span className="text-primary font-medium">{projectName}</span> 过滤。
            </>
          )}
        </p>
      </div>

      {/* 统计条 */}
      {!error && !isLoading && (
        <EcosystemStatsBar
          allProfiles={profiles}
          facetCounts={data?.facet_counts}
          total={data?.total}
        />
      )}

      {/* 筛选栏 */}
      <FilterBar
        filters={filters}
        onChange={setFilters}
        totalCount={filtered.length}
        facetCounts={data?.facet_counts}
      />

      {/* 列表区 */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading && (
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-44 rounded-lg" />
            ))}
          </div>
        )}

        {error && (
          <div
            className="flex items-start gap-2 p-4 rounded-lg border border-destructive/50 bg-destructive/10 text-destructive"
            role="alert"
          >
            <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" aria-hidden="true" />
            <div className="text-sm">
              <p className="font-medium">加载生态档案失败</p>
              <p className="mt-1 text-xs opacity-80">
                {error.message}
                {error.message.includes('Not Found') && (
                  <span className="block mt-1">
                    提示：API server 可能尚未注册 /api/ecosystem 路由，请确认后端已重启。
                  </span>
                )}
              </p>
            </div>
          </div>
        )}

        {!isLoading && !error && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 text-center text-muted-foreground">
            <Boxes className="h-10 w-10 opacity-30 mb-2" aria-hidden="true" />
            <p className="text-sm">暂无匹配的仓库</p>
            <p className="text-xs mt-1">
              {filters.keyword || filters.category || filters.minStars
                ? '调整筛选条件或清除过滤试试'
                : projectId
                  ? '当前项目下尚无生态仓档案，可切换到「全部项目」或运行扫描任务后填充'
                  : '运行扫描任务后将填充档案'}
            </p>
          </div>
        )}

        {!isLoading && !error && filtered.length > 0 && (
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map((repo) => (
              <RepoCard key={repo.id} repo={repo} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
