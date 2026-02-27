export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export interface DashboardMetrics {
    totalBatches: number;
    totalImages: number;
    validImages: number;
    totalDefects: number;
    successRate: number;
    qualityScore: number;
    recentBatches: { id: string, name: string, totalCaptures: number, validCaptures: number, qualityScore: number, defectCount: number }[];
    defectsRanking: { rank: number, code: string, label: string, count: number, severity: number, percentage: number }[];
    dailyStats: { date: string, volume: number, valid: number, defects: number }[];
    topDefects: { rank: number, code: string, label: string, count: number, severity: number, percentage: number }[];
    defectTrends: { name: string, count: number, date: string }[];
    errorDistribution: { name: string, value: number }[];
    validityDistribution: { name: string, value: number, color: string }[];
}

export interface Batch {
    id: string;
    name: string;
    description: string;
    total_captures: number;
    valid_captures?: number;
    invalid_captures?: number;
    total_defects: number;
    quality_score: number;
    created_at: string;
}

export interface Capture {
    id: string;
    filename: string;
    sha256?: string;
    is_valid: boolean;
    original_uri: string;
    processed_uri: string;
    processed_areas_uri?: string;
    processed_pins_uri?: string;
    processed_shaft_uri?: string;
    defects_count: number;
    hasMissingPins?: boolean;
    hasExtraPins?: boolean;
    hasDamagedPins?: boolean;
    hasWrongColorPins?: boolean;
    hasStructureDamage?: boolean;
    hasShaftDefects?: boolean;
}

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
    const res = await fetch(`${API_URL}/api/metrics/dashboard`, {
        cache: "no-store",
    });
    if (!res.ok) {
        throw new Error("Failed to fetch dashboard metrics");
    }
    return res.json();
}

export async function getBatches(): Promise<{ batches: Batch[], total: number }> {
    const res = await fetch(`${API_URL}/api/batches`, {
        cache: "no-store",
    });
    if (!res.ok) {
        throw new Error("Failed to fetch batches");
    }
    const data = await res.json();
    return { batches: data.batches, total: data.batches.length };
}

export async function getBatchDetails(batchId: string): Promise<{ batch: Batch, captures: Capture[] }> {
    const res = await fetch(`${API_URL}/api/batches/${batchId}`, {
        cache: "no-store",
    });
    if (!res.ok) {
        throw new Error("Failed to fetch batch details");
    }
    return res.json();
}

export async function deleteBatch(batchId: string): Promise<boolean> {
    const res = await fetch(`${API_URL}/api/batches/${batchId}`, {
        method: "DELETE",
    });
    if (!res.ok) {
        throw new Error("Failed to delete batch");
    }
    return true;
}
