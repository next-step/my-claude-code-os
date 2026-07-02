"use client";

// 적용된 필터 요약 칩. 필터 바가 길어져 스크롤돼도 "지금 무슨 조건인지"를 한 줄로
// 읽게 하고, 칩 하나씩 X 로 즉시 해제한다(동선 최소화). 활성 필터가 없으면 렌더 안 함.
// 값은 상위(FeedPage)가 소유 → 여기서는 변경만 통지(controlled). URL 동기화는 상위 책임.
import type { FeedFilters } from "@/lib/api";
import type { ExperienceLevel } from "@/types/contract";
import { experienceLabel, roleLabel } from "@/lib/format";
import { LOCATION_OPTIONS } from "@/types/contract";

interface Chip {
  key: string;
  label: string;
  /** 이 필터만 제거한 다음 FeedFilters */
  remove: () => Partial<FeedFilters>;
}

function locationLabel(v: string): string {
  return LOCATION_OPTIONS.find((o) => o.value === v)?.label ?? v;
}

export default function AppliedFilters({
  value,
  onChange,
  onReset,
}: {
  value: FeedFilters;
  onChange: (next: FeedFilters) => void;
  onReset: () => void;
}) {
  const chips: Chip[] = [];

  value.roles.forEach((r) =>
    chips.push({
      key: `role:${r}`,
      label: roleLabel(r) ?? r,
      remove: () => ({ roles: value.roles.filter((x) => x !== r) }),
    })
  );
  value.locations.forEach((l) =>
    chips.push({
      key: `loc:${l}`,
      label: locationLabel(l),
      remove: () => ({ locations: value.locations.filter((x) => x !== l) }),
    })
  );
  value.experiences.forEach((e) =>
    chips.push({
      key: `exp:${e}`,
      label: experienceLabel(e as ExperienceLevel),
      remove: () => ({ experiences: value.experiences.filter((x) => x !== e) }),
    })
  );
  if (value.keyword.trim()) {
    chips.push({
      key: "keyword",
      label: `"${value.keyword.trim()}"`,
      remove: () => ({ keyword: "" }),
    });
  }
  if (value.deadlineWithin != null) {
    chips.push({
      key: "deadline",
      label: `${value.deadlineWithin}일 이내 마감`,
      remove: () => ({ deadlineWithin: null }),
    });
  }
  if (value.includeExpired) {
    chips.push({
      key: "expired",
      label: "마감 지난 공고 포함",
      remove: () => ({ includeExpired: false }),
    });
  }

  if (chips.length === 0) return null;

  return (
    <div className="applied" aria-label="적용된 필터">
      <span className="applied__label">적용됨</span>
      <div className="applied__chips">
        {chips.map((c) => (
          <button
            key={c.key}
            type="button"
            className="chip chip--on chip--removable"
            onClick={() => onChange({ ...value, ...c.remove(), cursor: null })}
            aria-label={`${c.label} 필터 제거`}
          >
            {c.label}
            <span className="chip__x" aria-hidden="true">
              ×
            </span>
          </button>
        ))}
        <button
          type="button"
          className="applied__reset"
          onClick={onReset}
        >
          필터 전체 해제
        </button>
      </div>
    </div>
  );
}
