// ============================================================================
// SaraminAdapter — 사람인 공개 job-search API 어댑터 (OS.md 12.8 (1))
// ----------------------------------------------------------------------------
// - 공통 SourceAdapter 인터페이스만 준수(12.7 B-1: 소스 비종속. 인터페이스 변경 없음).
// - fetch 함수를 주입받는다: fixture 테스트(COLLECT_SOURCE=saramin-fixture)가
//   가짜 fetchFn 으로 "실 파싱 코드를 그대로" 태우기 위함. 실행 시엔 globalThis.fetch.
// - 요청 규약(12.8): job_mid_cd=2(IT개발·데이터) 고정, count=110, start 페이지 순회,
//   쿼터(하루 500콜) 보호를 위해 1회 실행당 최대 5콜.
//
// [법적/정책 유의 — 사람인 공개 API]
//  - 개발자센터 "이용신청 → 승인" 필수. 승인 전 실호출 불가(현재 fixture 로 검증).
//  - 약관: 재판매·대가 수취 금지. M1(단일 로컬·비상업 실습)은 무방. 공개 서비스화 시 재점검.
//  - 응답 필드명·구조는 승인 후 실응답으로 최종 검증한다(12.8). 이 어댑터는 필드가
//    없거나 형태가 달라도 throw 하지 않고 undefined 로 남긴다(→ Normalizer 가 PARTIAL 판정).
// ============================================================================

import type { RawJob, SourceAdapter } from "./source-adapter";

const API_URL = "https://oapi.saramin.co.kr/job-search";
/** 사람인 상위 직군 코드: 2 = IT개발·데이터 (M1 개발직군 한정, 12.8 고정) */
const JOB_MID_CD_IT = "2";
/** 요청당 최대 건수(사람인 상한 ≈ 110) */
const COUNT_PER_CALL = 110;
/** 쿼터 보호: 1회 실행당 최대 호출 수 (하루 500콜 대비, 12.8) */
export const MAX_CALLS_PER_RUN = 5;

export interface SaraminAdapterOptions {
  /** 사람인 개발자센터 발급 access-key */
  accessKey: string;
  /** 주입 가능한 fetch. 기본 globalThis.fetch. fixture 테스트는 가짜 fetchFn 주입 */
  fetchFn?: typeof globalThis.fetch;
}

// ---- 응답 파싱 헬퍼 (필드 누락/타입 변형에 관대 — 실패는 Normalizer 의 PARTIAL 로) ----

type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v !== null && typeof v === "object" ? (v as Dict) : {};
}

/** 문자열/숫자 → trim 된 문자열. 빈 값·기타 타입은 undefined */
function asStr(v: unknown): string | undefined {
  if (typeof v === "number") return String(v);
  if (typeof v !== "string") return undefined;
  const s = v.trim();
  return s === "" ? undefined : s;
}

export class SaraminAdapter implements SourceAdapter {
  readonly source = "saramin";

  private readonly accessKey: string;
  private readonly fetchFn: typeof globalThis.fetch;

  constructor({ accessKey, fetchFn = globalThis.fetch }: SaraminAdapterOptions) {
    if (!accessKey) {
      // 조용한 폴백 금지(12.8): 키 없이 생성 자체를 막는다.
      throw new Error("[saramin] accessKey 가 비어 있습니다.");
    }
    this.accessKey = accessKey;
    this.fetchFn = fetchFn;
  }

  /**
   * job-search 를 start=0 부터 페이지 순회하며 RawJob[] 수집.
   * 종료 조건: total 도달, 마지막 페이지(count 미만 반환), 또는 MAX_CALLS_PER_RUN 도달.
   */
  async fetchRaw(): Promise<RawJob[]> {
    const all: RawJob[] = [];

    for (let page = 0; page < MAX_CALLS_PER_RUN; page++) {
      const params = new URLSearchParams({
        "access-key": this.accessKey,
        job_mid_cd: JOB_MID_CD_IT,
        count: String(COUNT_PER_CALL),
        start: String(page),
      });
      const res = await this.fetchFn(`${API_URL}?${params.toString()}`, {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        // 부분 실패 허용: 이미 받은 페이지가 있으면 그것만 반환(수집은 idempotent 재시도 가능).
        if (all.length > 0) {
          console.warn(
            `[saramin] HTTP ${res.status} (start=${page}) — 이전 페이지까지 ${all.length}건으로 계속 진행`,
          );
          break;
        }
        throw new Error(`[saramin] API 요청 실패: HTTP ${res.status} (start=${page})`);
      }

      const body = asDict(await res.json());
      const jobs = asDict(body.jobs);
      // 사람인은 1건일 때 배열이 아닌 단일 객체를 줄 수 있어 방어적으로 배열화
      const rawList = jobs.job;
      const list: unknown[] = Array.isArray(rawList) ? rawList : rawList != null ? [rawList] : [];

      for (const item of list) {
        const raw = this.toRawJob(asDict(item));
        if (raw) all.push(raw);
      }

      const total = Number(asStr(jobs.total) ?? 0);
      if (list.length < COUNT_PER_CALL) break; // 마지막 페이지
      if (total > 0 && all.length >= total) break; // 전체 수집 완료
    }

    return all;
  }

  /**
   * 사람인 job 객체 → RawJob (12.8 매핑 계약).
   * id 가 없으면 upsert 키를 만들 수 없으므로 건너뛴다(경고 로그).
   */
  private toRawJob(job: Dict): RawJob | null {
    const sourceJobId = asStr(job.id);
    if (!sourceJobId) {
      console.warn("[saramin] id 없는 공고 응답 — 건너뜀:", JSON.stringify(job).slice(0, 200));
      return null;
    }

    const position = asDict(job.position);
    const companyDetail = asDict(asDict(job.company).detail);

    return {
      source: this.source,
      sourceJobId,
      // url 은 폴백 시에도 반드시 채운다(계약). 응답에 없으면 원문 view URL 을 구성.
      url:
        asStr(job.url) ??
        `https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=${sourceJobId}`,
      title: asStr(position.title),
      companyName: asStr(companyDetail.name),
      jobRoleCode: asStr(asDict(position["job-code"]).code),
      locationCode: asStr(asDict(position.location).code),
      experienceRaw: asStr(asDict(position["experience-level"]).code),
      employmentType: asStr(asDict(position["job-type"]).name),
      deadline: asStr(job["expiration-date"]),
      postedAt: asStr(job["posting-date"]),
      // description: 사람인 API 는 공고 본문 미제공 → 채우지 않음(프론트는 원문 URL 폴백)
      raw: job, // [A-3] 원본 job 객체 전체 보존(job-code.name·location.name·회사 힌트 포함)
    };
  }
}
