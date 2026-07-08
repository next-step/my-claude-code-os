// ============================================================================
// npm run collect — 수집 실행 진입점 (OS.md 12.2/12.7: M1 = 수동 실행)
// ----------------------------------------------------------------------------
// 파이프라인(12.8 (4) 고정):
//   adapter.fetchRaw() → normalizeRawJob() → prisma.job.upsert((source, sourceJobId))
//     → 수집 요약 로그(총·FULL·PARTIAL·신규/갱신)
//
// 수집 소스 스위치: COLLECT_SOURCE = mock(기본) | saramin-fixture | saramin
//   - mock            : MockAdapter (day-1, 승인 전 기본값)
//   - saramin-fixture : SaraminAdapter + 로컬 fixture 를 반환하는 가짜 fetchFn
//                       → 실 파싱·정규화·upsert 경로 전체를 승인 전에 검증
//   - saramin         : 실 API 호출. SARAMIN_ACCESS_KEY 필수(없으면 즉시 에러,
//                       조용한 폴백 금지 — 12.8)
//
// upsert 는 (source, sourceJobId) UNIQUE 키 기준 → 재실행 시 중복 생성 없음(idempotent).
// 날짜: Normalizer 는 ISO "문자열"을 반환하고, Date 변환은 여기(수집 진입점) 책임(12.8).
// ============================================================================

import { readFileSync } from "node:fs";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import { MockAdapter, type SourceAdapter } from "../src/lib/collect/source-adapter";
import { SaraminAdapter } from "../src/lib/collect/saramin-adapter";
import { normalizeRawJob } from "../src/lib/collect/normalizer";

const prisma = new PrismaClient();

const FIXTURE_PATH = path.resolve(
  process.cwd(),
  "src/lib/collect/fixtures/saramin-job-search.json",
);

/** COLLECT_SOURCE 값으로 어댑터 선택 (12.8 (4)) */
function buildAdapter(): SourceAdapter {
  const mode = process.env.COLLECT_SOURCE ?? "mock";

  switch (mode) {
    case "mock":
      return new MockAdapter();

    case "saramin-fixture": {
      // 가짜 fetchFn 이 fixture JSON 을 반환 → SaraminAdapter 의 실 파싱 코드를 그대로 태운다.
      const fixture = readFileSync(FIXTURE_PATH, "utf-8");
      const fetchFn: typeof globalThis.fetch = async () =>
        new Response(fixture, {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      return new SaraminAdapter({ accessKey: "fixture-key", fetchFn });
    }

    case "saramin": {
      const accessKey = process.env.SARAMIN_ACCESS_KEY;
      if (!accessKey) {
        // 조용한 폴백 금지(12.8): mock 으로 몰래 넘어가지 않고 명확히 실패시킨다.
        throw new Error(
          "[collect] COLLECT_SOURCE=saramin 인데 SARAMIN_ACCESS_KEY 가 없습니다. " +
            "사람인 개발자센터 승인 후 발급받은 키를 환경변수로 설정하세요. " +
            "(승인 전 검증은 COLLECT_SOURCE=saramin-fixture 사용)",
        );
      }
      return new SaraminAdapter({ accessKey });
    }

    default:
      throw new Error(
        `[collect] 알 수 없는 COLLECT_SOURCE: "${mode}" (mock | saramin-fixture | saramin)`,
      );
  }
}

async function main() {
  const mode = process.env.COLLECT_SOURCE ?? "mock";
  const adapter = buildAdapter();

  console.log(`[collect] mode=${mode} source=${adapter.source} 수집 시작`);
  const raws = await adapter.fetchRaw();
  console.log(`[collect] fetchRaw: ${raws.length}건 수신`);

  let full = 0;
  let partial = 0;
  let created = 0;
  let updated = 0;

  for (const raw of raws) {
    const input = normalizeRawJob(raw);
    if (input.dataQuality === "PARTIAL") partial += 1;
    else full += 1;

    // ISO 문자열 → Date 변환은 수집 진입점 책임(12.8). collectedAt 은 재수집 시각으로 갱신.
    const data = {
      url: input.url,
      title: input.title,
      companyName: input.companyName,
      jobRole: input.jobRole,
      location: input.location,
      experienceLevel: input.experienceLevel,
      employmentType: input.employmentType,
      deadline: input.deadline ? new Date(input.deadline) : null,
      postedAt: input.postedAt ? new Date(input.postedAt) : null,
      description: input.description,
      dataQuality: input.dataQuality,
      dedupKey: input.dedupKey,
      rawData: input.rawData,
      collectedAt: new Date(),
    };

    // 신규/갱신 집계용 존재 확인 (M1 수십 건 규모 — 정확성 우선, 성능 최적화는 불필요)
    const existing = await prisma.job.findUnique({
      where: {
        source_sourceJobId: { source: input.source, sourceJobId: input.sourceJobId },
      },
      select: { id: true },
    });

    await prisma.job.upsert({
      where: {
        source_sourceJobId: { source: input.source, sourceJobId: input.sourceJobId },
      },
      update: data,
      create: { source: input.source, sourceJobId: input.sourceJobId, ...data },
    });

    if (existing) updated += 1;
    else created += 1;
  }

  const dbTotal = await prisma.job.count();
  console.log(
    `[collect] 완료 — 수집 ${raws.length}건 (FULL ${full} / PARTIAL ${partial}) · ` +
      `신규 ${created} / 갱신 ${updated} · DB Job 총 ${dbTotal}건`,
  );
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
