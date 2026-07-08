// ============================================================================
// SourceAdapter — 공통 수집 인터페이스 (OS.md 12.2 / 12.7 B-1)
// ----------------------------------------------------------------------------
// [B-1] SaraminAdapter 를 특별취급하지 않는다. 모든 소스는 이 인터페이스만 준수한다.
//   → 사람인 API 승인 지연/실패 시 다른 소스 어댑터로 즉시 교체 가능(구조적 보험).
//
// 이번(M1 선행작업) 범위: 인터페이스 정의 + Mock 어댑터까지.
//   실 SaraminAdapter(공개 API 연동) + Normalizer 실구현은 다음 M1 작업.
//
// 폴백 전략(OS.md 7장): API → 크롤링 → URL. 어댑터 내부에서 흡수하고,
//   수집 실패 시 최소한 url 만 채운 RawJob 을 반환(→ Normalizer 가 PARTIAL 로 마킹).
// ============================================================================

/**
 * 정규화 이전 원본 공고.
 * Normalizer(RawJob → Job) 가 코드→라벨 매핑, dedupKey 계산, dataQuality 판정을 수행한다.
 */
export interface RawJob {
  /** 수집 소스 식별자("saramin" 등) */
  source: string;
  /** 소스 원본 ID (upsert 키 (source, sourceJobId) 의 일부) */
  sourceJobId: string;
  /** 원문 URL — 폴백 시에도 반드시 채운다 */
  url: string;

  // --- 있으면 채우는 정규화 힌트 필드(없으면 undefined → Normalizer 가 PARTIAL 판정) ---
  title?: string;
  companyName?: string;
  jobRoleCode?: string; // 소스별 직무 코드(예: 사람인 job_cd) → Normalizer 가 라벨 매핑
  locationCode?: string;
  experienceRaw?: string;
  employmentType?: string;
  deadline?: string; // ISO or 소스 원문
  postedAt?: string;
  description?: string;

  /**
   * [A-3] 원본 payload 통째로 보존.
   * 사업자번호/법인명 원문 등 회사 식별 힌트가 응답에 있으면 버리지 않는다.
   * Normalizer 가 Job.rawData 에 JSON.stringify 하여 저장 → M2 DART 공시 연결에 사용.
   */
  raw: Record<string, unknown>;
}

/** 모든 수집 소스가 구현하는 공통 계약 */
export interface SourceAdapter {
  /** 소스 식별자. Job.source 로 저장됨 */
  readonly source: string;
  /**
   * 원본 공고 수집. 내부에서 폴백(API→크롤링→URL)을 흡수한다.
   * @param params 소스별 조회 조건(직무 코드, 페이지 등). M1 개발직군 한정.
   */
  fetchRaw(params?: Record<string, unknown>): Promise<RawJob[]>;
}

// ----------------------------------------------------------------------------
// MockAdapter — day-1 용. 사람인 API 이용신청/승인 전까지 이걸로 파이프라인을 돌린다.
//
// [사람인 공개 API 유의 — README/주석 기록]
//   - 실연동에는 사람인 개발자센터 "이용신청 → 승인" 이 필요하다.
//   - 쿼터: 하루 500 콜, 요청당 count ≈ 110 상한.
//   - 약관: 재판매·대가 수취 금지. M1(단일 로컬·비상업 실습)은 무방. 공개 서비스화 시 재점검.
//   - robots/이용약관 점검은 실 어댑터 연동 시점에 최종 확인.
// ----------------------------------------------------------------------------
export class MockAdapter implements SourceAdapter {
  readonly source = "saramin";

  async fetchRaw(): Promise<RawJob[]> {
    // 실제로는 사람인 API fetch 결과. 여기서는 정규화 입력 형태만 예시로 반환.
    return [
      {
        source: "saramin",
        sourceJobId: "SR-1001",
        url: "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=1001",
        title: "백엔드 개발자 (Node.js/TypeScript) 신입",
        companyName: "토스뱅크",
        jobRoleCode: "TBD-be",
        locationCode: "101000", // 예: 서울 지역코드(placeholder)
        experienceRaw: "신입",
        employmentType: "정규직",
        deadline: "2026-07-05",
        postedAt: "2026-06-20",
        // [주의] 이 mock 은 seed 데이터(SR-1001)와 같은 upsert 키를 가리킨다.
        //   collect(mock) 재실행이 seed 행을 훼손하지 않도록 seed 와 동일 description 유지.
        //   (실 사람인 API 는 본문 미제공 → 실 어댑터에서는 description 없음)
        description:
          "Node.js/TypeScript 기반 결제 백엔드 API 개발. REST/gRPC, PostgreSQL, 대용량 트래픽 경험 우대.",
        raw: {
          // [A-3] 회사 식별 힌트가 응답에 있으면 여기에 원문 보존
          company: { name: "토스뱅크", corp_no: null, biz_no: null },
          // Normalizer 의 name 기반 라벨 매핑(12.8)이 mock 에서도 동작하도록
          // 사람인 응답과 같은 위치(position.*.name)에 name 힌트를 담는다.
          position: {
            "job-code": { code: "TBD-be", name: "웹개발, 백엔드/서버개발" },
            location: { code: "101000", name: "서울 > 전체" },
          },
          _note: "실 연동 시 사람인 응답 원본을 그대로 담는다",
        },
      },
    ];
  }
}
