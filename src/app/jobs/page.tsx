"use client";

// ============================================================================
// 공고 피드 (M1 핵심 화면)
// ----------------------------------------------------------------------------
// 온보딩 조건을 초기 필터 프리셋으로 받아 "내 조건 N건"을 한눈에.
// - 마감임박순 기본 정렬(상시는 항상 맨 뒤)
// - PARTIAL 공고 전용 카드 + 필터로 가려진 partialHiddenCount 접이식 노출
// - 북마크 토글(클라이언트 스토어) / 커서 더보기 / 로딩·빈·에러 상태
// ============================================================================

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { JobDTO, UserPreference } from "@/types/contract";
import { DEV_ROLE_OPTIONS, LOCATION_OPTIONS } from "@/types/contract";
import {
  DEFAULT_FILTERS,
  fetchJobs,
  fetchPreferences,
  buildJobsQuery,
  filtersFromParams,
  hasFilterParams,
  ApiRequestError,
  type FeedFilters,
} from "@/lib/api";
import Filters from "@/components/Filters";
import AppliedFilters from "@/components/AppliedFilters";
import JobCard from "@/components/JobCard";
import { CardSkeletonList, EmptyState, ErrorState } from "@/components/states";

/** 온보딩 조건 → 피드 초기 필터 프리셋 */
function presetFromPreference(pref: UserPreference): FeedFilters {
  // 신입/경력 지원자 모두 "경력무관(ANY)" 공고는 관련이 크므로 함께 포함한다.
  const experiences =
    pref.experience === "ANY"
      ? []
      : pref.experience === "NEW"
      ? ["NEW", "ANY"]
      : ["EXPERIENCED", "ANY"];
  return {
    ...DEFAULT_FILTERS,
    // 선호 직무 전체를 합집합(OR)으로 프리셋(role 콤마 다중값 지원, 12.6)
    roles: pref.roles.filter((r) =>
      DEV_ROLE_OPTIONS.some((o) => o.value === r)
    ),
    locations: pref.locations.filter((l) =>
      LOCATION_OPTIONS.some((o) => o.value === l)
    ),
    experiences,
    keyword: pref.keywords[0] ?? "",
  };
}

function FeedInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState<FeedFilters>(DEFAULT_FILTERS);
  const [filtersReady, setFiltersReady] = useState(false);

  const [items, setItems] = useState<JobDTO[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [partialHiddenCount, setPartialHiddenCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPartial, setShowPartial] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0); // 에러 재시도용(같은 필터 강제 refetch)

  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 1) 최초 필터 확정: URL이 진실. 필터 쿼리가 있으면 그대로 복원(새로고침·공유 안전),
  //    없으면(깨끗한 URL) 온보딩 조건을 프리셋으로. 프리셋 로드 실패해도 기본 필터로 진행.
  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    if (hasFilterParams(params)) {
      setFilters(filtersFromParams(params));
      setFiltersReady(true);
      return;
    }
    let alive = true;
    fetchPreferences()
      .then((pref) => {
        if (alive) setFilters(presetFromPreference(pref));
      })
      .catch(() => {
        /* 프리셋 실패 시 기본 필터 유지 */
      })
      .finally(() => {
        if (alive) setFiltersReady(true);
      });
    return () => {
      alive = false;
    };
    // 최초 1회만 URL/프리셋으로 초기화. 이후 변경은 applyFilters 가 URL 로 동기화.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 필터 변경의 단일 관문: 상태 갱신 + URL 동기화(replace, 히스토리 오염/스크롤 튐 방지).
  // buildJobsQuery 는 API 쿼리와 동일 직렬화 규약 → URL 이 곧 JobsQuery.
  const applyFilters = useCallback(
    (next: FeedFilters) => {
      setFilters(next);
      const qs = buildJobsQuery({ ...next, cursor: null });
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname]
  );

  // 목록 새로 로드(필터 변경 시). cursor=null 로 첫 페이지.
  const listKey = buildJobsQuery({ ...filters, cursor: null });
  useEffect(() => {
    if (!filtersReady) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setLoading(true);
    setError(null);
    debounceRef.current = setTimeout(() => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      fetchJobs({ ...filters, cursor: null }, ctrl.signal)
        .then((res) => {
          setItems(res.items);
          setTotalCount(res.totalCount);
          setPartialHiddenCount(res.partialHiddenCount);
          setNextCursor(res.nextCursor);
        })
        .catch((e) => {
          if (e?.name === "AbortError") return;
          setError(
            e instanceof ApiRequestError
              ? e.message
              : "공고를 불러오지 못했어요. 네트워크를 확인해 주세요."
          );
        })
        .finally(() => setLoading(false));
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // listKey 로 필터 변화를 감지(문자열이므로 안정적). reloadNonce 로 재시도 강제.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listKey, filtersReady, reloadNonce]);

  const loadMore = useCallback(() => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    fetchJobs({ ...filters, cursor: nextCursor })
      .then((res) => {
        setItems((prev) => [...prev, ...res.items]);
        setNextCursor(res.nextCursor);
      })
      .catch(() => {
        /* 더보기 실패는 조용히 무시(버튼 유지) */
      })
      .finally(() => setLoadingMore(false));
  }, [filters, nextCursor, loadingMore]);

  const resetFilters = () => applyFilters(DEFAULT_FILTERS);

  // partialHiddenCount 펼침 → 이 공고들을 실제로 보이게: 직무/지역 필터 해제
  const revealPartial = () =>
    applyFilters({ ...filters, roles: [], locations: [], cursor: null });

  return (
    <div className="page">
      <div className="pageHead">
        <div>
          <h1 className="pageHead__title">공고 피드</h1>
          <p className="pageHead__sub">
            {loading ? (
              "내 조건에 맞는 공고를 모으는 중…"
            ) : (
              <>
                내 조건 <strong>{totalCount}건</strong> · 여러 사이트를 한 곳에서
              </>
            )}
          </p>
        </div>
        <Link href="/onboarding" className="btn btn--ghost btn--sm">
          내 조건 수정
        </Link>
      </div>

      <Filters value={filters} onChange={applyFilters} onReset={resetFilters} />

      <AppliedFilters
        value={filters}
        onChange={applyFilters}
        onReset={resetFilters}
      />

      {/* PARTIAL 접이식 배너 — 모아보기 가치 보호 */}
      {partialHiddenCount > 0 && (
        <div className="partialBanner">
          <button
            type="button"
            className="partialBanner__toggle"
            aria-expanded={showPartial}
            onClick={() => setShowPartial((v) => !v)}
          >
            <span aria-hidden="true">{showPartial ? "▾" : "▸"}</span>
            현재 조건으로 확인이 어려운 공고 {partialHiddenCount}건
          </button>
          {showPartial && (
            <div className="partialBanner__body">
              <p>
                자동 수집이 제한돼 직무·지역 정보가 비어 있는 공고예요. 조건 필터에
                걸려 가려졌지만, 놓치지 않도록 알려드려요.
              </p>
              <button
                type="button"
                className="btn btn--outline btn--sm"
                onClick={revealPartial}
              >
                직무·지역 필터 풀고 이 공고들도 보기
              </button>
            </div>
          )}
        </div>
      )}

      {/* 본문 상태 분기 */}
      {loading ? (
        <CardSkeletonList count={4} />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={() => setReloadNonce((n) => n + 1)}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="조건에 맞는 공고가 없어요"
          description="필터를 넓히거나 초기화해 보세요. 마감 지난 공고를 포함할 수도 있어요."
          action={
            <button className="btn btn--primary" onClick={resetFilters}>
              필터 전체 해제
            </button>
          }
        />
      ) : (
        <>
          <ul className="cardList">
            {items.map((job) => (
              <li key={job.id}>
                <JobCard job={job} />
              </li>
            ))}
          </ul>
          {nextCursor && (
            <div className="feedMore">
              <button
                type="button"
                className="btn btn--outline"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore ? "불러오는 중…" : "더 보기"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// useSearchParams(초기 URL 필터 복원) 는 App Router 에서 Suspense 경계를 요구한다.
export default function FeedPage() {
  return (
    <Suspense
      fallback={
        <div className="page">
          <div className="pageHead">
            <h1 className="pageHead__title">공고 피드</h1>
          </div>
          <CardSkeletonList count={4} />
        </div>
      }
    >
      <FeedInner />
    </Suspense>
  );
}
