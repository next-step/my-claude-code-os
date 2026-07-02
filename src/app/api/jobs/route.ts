// ============================================================================
// GET /api/jobs  — 실 DB(Prisma) 기반. OS.md 12.5/12.6 계약.
// ----------------------------------------------------------------------------
// 데이터는 seed 된 dev.db 의 Job. 응답 계약(JobDTO[], nextCursor, totalCount,
// partialHiddenCount)은 이전 mock 과 동일 → 프론트 무수정.
//
// 쿼리(12.5): role(콤마 다중), location(콤마 다중), experience(콤마 다중),
//   keyword, sort(deadline|recent), deadlineWithin(days), includeExpired(기본 false), cursor
//
// [설계 결정]
//  - 하드 필터(expired/experience/keyword/deadlineWithin)는 Prisma WHERE 로 DB 에서 처리.
//  - role/location 다중값 + PARTIAL 보호(null 필드로 가려지는 PARTIAL 카운트)는
//    DB 조회 후 애플리케이션에서 처리. M1 데이터 규모(수십 건)에서 정확·단순.
//    이유: partialHiddenCount 는 "null 때문에 가려진 PARTIAL"만 세야 하므로
//    단순 WHERE 로는 FULL 탈락과 구분이 안 됨.
//  - 정렬: deadline=null(상시)은 항상 맨 뒤(12.6). recent 는 postedAt 내림차순 +
//    postedAt=null 항상 맨 뒤(deadline 규약과 대칭). Prisma nulls 옵션의 SQLite 지원이
//    불확실하여 정렬을 앱에서 명시적으로 수행(계약 정확성 우선).
//  - 집계(12.6): totalCount = 필터·includeExpired 적용 후 매칭 전체 수(PARTIAL 숨김 반영 전)
//    = kept + partialHidden. partialHiddenCount 는 그 부분집합. 따라서 items 는 kept 만
//    페이지네이션하지만 totalCount 에는 숨긴 PARTIAL 도 포함한다.
//  - 미지의 필터값(카탈로그 밖 role/location/experience)은 조용히 무시(500 금지):
//    membership 검사(includes / DB in) 특성상 미지값은 어떤 공고와도 매칭되지 않아
//    자연히 걸러진다. 모든 값이 미지여도 items:[] 로 정상 응답(예외 아님).
// ============================================================================

import { NextRequest, NextResponse } from "next/server";
import type { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { toJobDTO, JOB_INCLUDE, type JobWithBookmarks } from "@/lib/serialize";
import type { JobsListResponse } from "@/types/contract";

const PAGE_SIZE = 20;

function splitMulti(v: string | null): string[] {
  if (!v) return [];
  return v
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** 오늘 0시(UTC) — 당일 마감 공고를 만료로 제외하지 않기 위한 경계 */
function startOfToday(): Date {
  const n = new Date();
  return new Date(Date.UTC(n.getUTCFullYear(), n.getUTCMonth(), n.getUTCDate()));
}

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;

  const roles = splitMulti(sp.get("role")); // 콤마 다중값 (location/experience 와 동일 규약)
  const locations = splitMulti(sp.get("location"));
  const experiences = splitMulti(sp.get("experience"));
  const keyword = sp.get("keyword")?.trim() ?? "";
  const sort = sp.get("sort") === "recent" ? "recent" : "deadline";
  const deadlineWithinRaw = sp.get("deadlineWithin");
  const deadlineWithin =
    deadlineWithinRaw != null && deadlineWithinRaw !== ""
      ? Number(deadlineWithinRaw)
      : null;
  const includeExpired = sp.get("includeExpired") === "true";
  const cursor = sp.get("cursor");

  const today = startOfToday();

  // --- DB 하드 필터 ---
  const and: Prisma.JobWhereInput[] = [];

  // 마감 지난 공고 기본 제외(12.6). 상시(deadline=null)는 만료 아님.
  if (!includeExpired) {
    and.push({ OR: [{ deadline: null }, { deadline: { gte: today } }] });
  }
  if (experiences.length > 0) {
    and.push({ experienceLevel: { in: experiences } });
  }
  if (keyword) {
    and.push({
      OR: [
        { title: { contains: keyword } },
        { companyName: { contains: keyword } },
        { description: { contains: keyword } },
      ],
    });
  }
  // N일 이내 마감. deadline 있는 공고에만 적용, null(상시)은 통과.
  if (deadlineWithin != null && !Number.isNaN(deadlineWithin)) {
    const until = new Date(today.getTime() + deadlineWithin * 86_400_000);
    and.push({ OR: [{ deadline: null }, { deadline: { lte: until } }] });
  }

  const where: Prisma.JobWhereInput = and.length > 0 ? { AND: and } : {};

  const rows = await prisma.job.findMany({ where, include: JOB_INCLUDE });

  // --- role/location 다중값 필터 + PARTIAL 보호(12.6) ---
  let partialHiddenCount = 0;
  const kept: JobWithBookmarks[] = [];
  for (const job of rows) {
    const hideByRole = roles.length > 0 && job.jobRole == null;
    const hideByLoc = locations.length > 0 && job.location == null;
    if (job.dataQuality === "PARTIAL" && (hideByRole || hideByLoc)) {
      partialHiddenCount += 1; // 조건 확인 어려운 공고로 별도 노출 → 모아보기 가치 보호
      continue;
    }
    if (roles.length > 0 && (!job.jobRole || !roles.includes(job.jobRole)))
      continue;
    if (
      locations.length > 0 &&
      (!job.location || !locations.includes(job.location))
    )
      continue;
    kept.push(job);
  }

  // --- 정렬(12.6) ---
  kept.sort((a, b) => {
    if (sort === "recent") {
      // 최신순: postedAt 내림차순. null 은 항상 맨 뒤 → -Infinity 로 명시(deadline 규약과 대칭).
      // 둘 다 null 이면 -Infinity===-Infinity 라 pb!==pa 가 false → NaN 비교 없이 id tiebreak 로.
      const pa = a.postedAt ? a.postedAt.getTime() : -Infinity;
      const pb = b.postedAt ? b.postedAt.getTime() : -Infinity;
      if (pb !== pa) return pb - pa;
      return a.id < b.id ? -1 : 1; // 커서 (postedAt, id) 복합의 2차 키
    }
    // deadline: 마감임박순, deadline=null(상시)은 항상 맨 뒤
    const da = a.deadline ? a.deadline.getTime() : Infinity;
    const db = b.deadline ? b.deadline.getTime() : Infinity;
    if (da !== db) return da - db;
    return a.id < b.id ? -1 : 1;
  });

  // --- 커서 페이지네이션 (정렬 후 id 기준) ---
  let startIdx = 0;
  if (cursor) {
    const idx = kept.findIndex((j) => j.id === cursor);
    startIdx = idx >= 0 ? idx + 1 : 0;
  }
  const page = kept.slice(startIdx, startIdx + PAGE_SIZE);
  const nextCursor =
    startIdx + PAGE_SIZE < kept.length ? page[page.length - 1].id : null;

  const body: JobsListResponse = {
    items: page.map(toJobDTO),
    nextCursor,
    // 12.6: PARTIAL 숨김 반영 전 매칭 전체 수 = 표시분(kept) + 숨긴 PARTIAL.
    // partialHiddenCount 가 이 값의 부분집합이 되도록 반드시 합산한다.
    totalCount: kept.length + partialHiddenCount,
    partialHiddenCount,
  };
  return NextResponse.json(body);
}
