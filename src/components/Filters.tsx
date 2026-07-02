"use client";

// 피드 필터 바. 온보딩 조건이 초기 프리셋으로 들어오고, 사용자가 언제든 변경(OS 6장).
// 값은 상위(FeedPage)가 소유하고 여기서는 변경만 통지한다(controlled).
import {
  DEV_ROLE_OPTIONS,
  EXPERIENCE_OPTIONS,
  LOCATION_OPTIONS,
} from "@/types/contract";
import type { FeedFilters } from "@/lib/api";

const DEADLINE_PRESETS: { label: string; value: number | null }[] = [
  { label: "전체", value: null },
  { label: "3일 이내", value: 3 },
  { label: "7일 이내", value: 7 },
];

export default function Filters({
  value,
  onChange,
  onReset,
}: {
  value: FeedFilters;
  onChange: (next: FeedFilters) => void;
  onReset: () => void;
}) {
  const patch = (p: Partial<FeedFilters>) =>
    onChange({ ...value, ...p, cursor: null });

  const toggleIn = (list: string[], v: string) =>
    list.includes(v) ? list.filter((x) => x !== v) : [...list, v];

  return (
    <section className="filters" aria-label="공고 필터">
      {/* 정렬 — 마감임박순이 기본이자 핵심 */}
      <div className="filters__row">
        <span className="filters__label">정렬</span>
        <div className="segmented" role="group" aria-label="정렬 기준">
          <button
            type="button"
            className={`segmented__btn${
              value.sort === "deadline" ? " segmented__btn--on" : ""
            }`}
            aria-pressed={value.sort === "deadline"}
            onClick={() => patch({ sort: "deadline" })}
          >
            마감임박순
          </button>
          <button
            type="button"
            className={`segmented__btn${
              value.sort === "recent" ? " segmented__btn--on" : ""
            }`}
            aria-pressed={value.sort === "recent"}
            onClick={() => patch({ sort: "recent" })}
          >
            최신순
          </button>
        </div>
      </div>

      {/* 직무 — 다중(콤마 OR). 온보딩의 복수 직무가 그대로 반영됨 */}
      <div className="filters__row filters__row--wrap">
        <span className="filters__label">직무</span>
        <div className="chips">
          {DEV_ROLE_OPTIONS.map((o) => {
            const on = value.roles.includes(o.value);
            return (
              <button
                key={o.value}
                type="button"
                className={`chip${on ? " chip--on" : ""}`}
                aria-pressed={on}
                onClick={() => patch({ roles: toggleIn(value.roles, o.value) })}
              >
                {o.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 지역 — 다중 */}
      <div className="filters__row filters__row--wrap">
        <span className="filters__label">지역</span>
        <div className="chips">
          {LOCATION_OPTIONS.map((o) => {
            const on = value.locations.includes(o.value);
            return (
              <button
                key={o.value}
                type="button"
                className={`chip${on ? " chip--on" : ""}`}
                aria-pressed={on}
                onClick={() =>
                  patch({ locations: toggleIn(value.locations, o.value) })
                }
              >
                {o.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 경력 — 다중 */}
      <div className="filters__row filters__row--wrap">
        <span className="filters__label">경력</span>
        <div className="chips">
          {EXPERIENCE_OPTIONS.map((o) => {
            const on = value.experiences.includes(o.value);
            return (
              <button
                key={o.value}
                type="button"
                className={`chip${on ? " chip--on" : ""}`}
                aria-pressed={on}
                onClick={() =>
                  patch({ experiences: toggleIn(value.experiences, o.value) })
                }
              >
                {o.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 마감 임박 빠른 필터 + 키워드 + 마감 포함 */}
      <div className="filters__row filters__row--wrap">
        <span className="filters__label">마감</span>
        <div className="chips">
          {DEADLINE_PRESETS.map((p) => {
            const on = value.deadlineWithin === p.value;
            return (
              <button
                key={String(p.value)}
                type="button"
                className={`chip${on ? " chip--on" : ""}`}
                aria-pressed={on}
                onClick={() => patch({ deadlineWithin: p.value })}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="filters__row filters__row--wrap">
        <label className="filters__label" htmlFor="f-keyword">
          키워드
        </label>
        <input
          id="f-keyword"
          className="input"
          type="search"
          placeholder="예: TypeScript, React"
          value={value.keyword}
          onChange={(e) => patch({ keyword: e.target.value })}
        />
        <label className="checkbox">
          <input
            type="checkbox"
            checked={value.includeExpired}
            onChange={(e) => patch({ includeExpired: e.target.checked })}
          />
          마감 지난 공고 포함
        </label>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onReset}>
          필터 전체 해제
        </button>
      </div>
    </section>
  );
}
