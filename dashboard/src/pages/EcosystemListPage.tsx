import { useState, useMemo, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, Boxes, ChevronLeft, ChevronRight, Search as SearchIcon } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { useEcosystemProfiles } from '@/api/ecosystem';
import type { EcosystemFilters } from '@/api/ecosystem';
import { RepoCard } from '@/components/ecosystem/RepoCard';
import { FilterBar } from '@/components/ecosystem/FilterBar';
import { EcosystemStatsBar } from '@/components/ecosystem/EcosystemStatsBar';
import { RecentScanRunsBar } from '@/components/ecosystem/RecentScanRunsBar';
import { useProject } from '@/context/ProjectContext';

type LifecycleTab = 'active' | 'all' | 'deleted';

/**
 * Ecosystem 列表页 — v1.5.0-E：stage 徽章 + 活跃/全量/已删除 tab。
 * 路径：/ecosystem
 * 数据源：GET /api/ecosystem/profiles?facet_counts=true&is_active=...&is_deleted=...
 */
const PAGE_SIZE = 100;

export function EcosystemListPage() {
  const { projectId, projectName } = useProject();
  const [tab, setTab] = useState<LifecycleTab>('active');
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<EcosystemFilters>({
    limit: PAGE_SIZE,
    facetCounts: true,
  });

  // tab / 筛选条件变化时重置到第 1 页（防止 page=3 但只剩 50 条空白）
  useEffect(() => {
    setPage(1);
  }, [tab, filters]);

  // 根据 tab 注入活跃/已删除参数 + 分页 offset
  const effectiveFilters = useMemo<EcosystemFilters>(() => {
    const base: EcosystemFilters = { ...filters, offset: (page - 1) * PAGE_SIZE };
    if (tab === 'active') return { ...base, isActive: true, isDeleted: false };
    if (tab === 'deleted') return { ...base, isDeleted: true };
    return base; // all: 不限定 active/deleted
  }, [filters, tab, page]);

  const { data, isLoading, error } = useEcosystemProfiles(effectiveFilters);
  const profiles = data?.profiles ?? [];

  // 客户端二次过滤：keyword 也匹配 owner/description
  const filtered = useMemo(() => {
    if (!filters.keyword) return profiles;
    const q = filters.keyword.toLowerCase();
    return profiles.filter(
      (p) =>
        p.repo_full_name.toLowerCase().includes(q) ||
        (p.owner ?? '').toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q) ||
        (p.description ?? p.description_excerpt ?? '').toLowerCase().includes(q) ||
        (p.one_line_summary ?? '').toLowerCase().includes(q),
    );
  }, [profiles, filters.keyword]);

  return (
    <div className="flex h-full flex-col">
      {/* 页头 */}
      <div className="border-b px-6 py-4 bg-background">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
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
          <Button
            variant="outline"
            size="sm"
            className="shrink-0"
            nativeButton={false}
            render={<Link to="/ecosystem/research" />}
          >
            <SearchIcon className="mr-1 h-4 w-4" aria-hidden="true" />
            查找候选
          </Button>
        </div>

        {/* 活跃/全量/已删除 tab */}
        <Tabs
          value={tab}
          onValueChange={(v: string) => setTab(v as LifecycleTab)}
          className="mt-3"
        >
          <TabsList variant="line" className="gap-2">
            <TabsTrigger value="active" aria-label="活跃集">
              活跃集
            </TabsTrigger>
            <TabsTrigger value="all" aria-label="全量">
              全量
            </TabsTrigger>
            <TabsTrigger value="deleted" aria-label="已删除">
              已删除
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* 最近批次扫描概览（v1.5.2: 从单仓详情页迁回生态档案级位置） */}
      <RecentScanRunsBar />

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
                : tab === 'deleted'
                  ? '本项目尚未识别到已删除/被设私有的仓'
                  : tab === 'active'
                    ? '当前活跃集为空，可切换到「全量」查看所有归档仓'
                    : projectId
                      ? '当前项目下尚无生态仓档案，可切换到「全部项目」或运行扫描任务后填充'
                      : '运行扫描任务后将填充档案'}
            </p>
          </div>
        )}

        {!isLoading && !error && filtered.length > 0 && (
          <>
            <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filtered.map((repo) => (
                <RepoCard key={repo.id} repo={repo} />
              ))}
            </div>

            {/* 分页器：仅在总数超过单页时显示 */}
            {(data?.total ?? 0) > PAGE_SIZE && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <div className="text-sm text-muted-foreground">
                  第 <span className="font-medium text-foreground">{(page - 1) * PAGE_SIZE + 1}</span>
                  {' - '}
                  <span className="font-medium text-foreground">
                    {Math.min(page * PAGE_SIZE, data?.total ?? 0)}
                  </span>
                  {' '}/ 共 <span className="font-medium text-foreground">{data?.total ?? 0}</span> 仓
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="h-4 w-4 mr-1" aria-hidden="true" />
                    上一页
                  </Button>
                  <span className="text-sm text-muted-foreground px-2">
                    第 {page} / {Math.ceil((data?.total ?? 0) / PAGE_SIZE)} 页
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={!data?.has_more}
                  >
                    下一页
                    <ChevronRight className="h-4 w-4 ml-1" aria-hidden="true" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
