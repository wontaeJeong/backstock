import { z } from "zod"

const envelope = z.object({
  code: z.string().optional(),
  message: z.string().optional(),
  details: z.object({ issues: z.array(z.object({ code: z.string() })).optional() }).optional(),
})

const issues: Record<string, string> = {
  normalization_error:
    "날짜·시간대·필수 컬럼·숫자 형식을 확인하세요. 분봉은 bar 종료 시각과 명시적 UTC offset이 필요합니다.",
  duplicate_timestamp: "중복된 시각이 있습니다. 종목별 timestamp는 한 번만 포함해야 합니다.",
  out_of_order: "데이터 시각이 순서대로 정렬되어 있지 않습니다.",
  outside_request_range:
    "선택한 기간 밖의 행이 있습니다. 파일 전체 범위에 맞게 시작일·종료일을 수정하세요. 종료일은 포함하지 않습니다.",
  empty_dataset: "선택한 기간에 데이터가 없습니다. 파일과 기간을 확인하세요.",
  incomplete_range: "요청한 기간의 데이터가 충분하지 않습니다.",
  non_positive_price: "가격은 0보다 커야 합니다.",
  invalid_ohlc: "고가·저가·시가·종가의 범위가 일치하지 않습니다.",
  negative_volume: "거래량은 음수일 수 없습니다.",
  adjustment_mismatch: "파일의 가격·거래량 보정 의미와 선택한 설정이 다릅니다.",
  corporate_action_mismatch: "분할·배당 정보와 가격·거래량의 일관성을 확인하세요.",
  unsupported_price_precision: "가격의 숫자 자릿수가 저장 가능한 범위를 초과합니다.",
}

export function apiErrorMessage(value: unknown, status: number): string {
  const parsed = envelope.safeParse(value)
  if (!parsed.success) return "요청에 실패했습니다. 입력값과 서버 상태를 확인하세요."
  const data = parsed.data
  if (data.code === "DATASET_INVALID") {
    const explanations = [
      ...new Set(
        (data.details?.issues ?? []).map(
          (issue) =>
            issues[issue.code] ??
            "파일 데이터 검증을 통과하지 못했습니다. 컬럼·기간·주기를 확인하세요.",
        ),
      ),
    ]
    return (
      explanations.slice(0, 4).join(" ") ||
      "파일 데이터 검증에 실패했습니다. 컬럼·시간대·기간을 확인하세요."
    )
  }
  if (status === 413) return "파일 또는 요청 크기가 허용 범위를 초과했습니다."
  if (status === 415) return "CSV 또는 Parquet 파일과 해당 확장자를 사용하세요."
  if (data.code === "VALIDATION_ERROR") return "종목·기간·주기와 필수 입력값을 확인하세요."
  if (data.code === "NOT_FOUND") return "요청한 데이터 또는 실행 결과를 찾을 수 없습니다."
  if (data.code === "HTTP_ERROR") return "요청 형식이 올바르지 않습니다. 파일과 설정을 확인하세요."
  return data.message ?? "요청에 실패했습니다. 입력값과 서버 상태를 확인하세요."
}
