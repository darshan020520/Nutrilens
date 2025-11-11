// Inventory Dashboard Types
// Based on actual backend API responses

export interface InventoryItem {
  id: number;
  item_id: number;
  item_name: string;
  category: string;
  quantity_grams: number;
  expiry_date: string | null;
  days_until_expiry: number | null;
  is_depleted: boolean;
}

export interface InventoryStatus {
  total_items: number;
  total_weight_g: number;
  expiring_soon: Array<{
    item_name: string;
    quantity_grams: number;
    days_until_expiry: number;
  }>;
  low_stock: Array<{
    item_name: string;
    quantity_grams: number;
    category: string;
  }>;
  categories: Record<string, number>;
  nutritional_capacity: {
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    calories: number;
  };
  estimated_days_remaining: number;
  ai_recommendations: string[];
}

export interface AddItemsResult {
  status: string;
  results: {
    successful: Array<{
      original: string;
      matched: string;
      quantity: string;
      confidence: number;
    }>;
    needs_confirmation: Array<{
      original: string;
      suggested: string | null;
      item_id?: number;
      confidence: number;
      quantity?: number;
      unit?: string;
    }>;
    failed: Array<{
      original: string;
      reason: string;
    }>;
    summary: {
      successful: number;
      needs_confirmation: number;
      failed: number;
    };
  };
  message: string;
}

export interface ReceiptUploadResult {
  receipt_id: number;
  status: string;
  image_url: string;
  total_items: number;
  auto_added_count: number;
  auto_added: Array<{
    item_name: string;
    quantity: number;
    unit: string;
  }>;
  needs_confirmation_count: number;
  needs_confirmation: Array<{
    item_name: string;
    quantity: number;
    unit: string;
    suggested_item_id: number | null;
    suggested_item_name: string | null;
    confidence: number;
  }>;
}

export interface PendingItem {
  id: number;
  receipt_id: number;
  item_name: string;
  quantity: number;
  unit: string;
  suggested_item_id: number | null;
  suggested_item_name: string | null;
  confidence: number;
}

// Enriched receipt pending item (from new enrichment pipeline)
export interface EnrichedPendingItem {
  id: number;
  item_name: string; // Original from receipt
  quantity: number;
  unit: string;
  // Enrichment data from FDC + LLM pipeline
  canonical_name: string | null;
  category: string | null;
  fdc_id: string | null;
  nutrition_data: {
    protein_g?: number;
    fat_g?: number;
    carbs_g?: number;
    calories?: number;
    fiber_g?: number;
    sodium_mg?: number;
  } | null;
  enrichment_confidence: number | null;
  enrichment_reasoning: string | null;
}

export interface ReceiptPendingItemsResponse {
  receipt_id: number;
  count: number;
  items: EnrichedPendingItem[];
}

export interface ConfirmAndSeedResponse {
  status: string;
  seeded_count: number;
  added_count: number;
  seeded_items: Array<{
    canonical_name: string;
    category: string;
    item_id: number;
  }>;
}

export interface MakeableRecipe {
  recipe_id: number;
  name: string;
  can_make: boolean;
  missing_ingredients: string[];
  available_ingredients: string[];
  estimated_servings: number;
}

export interface ExpiringItem {
  inventory_id: number;
  item_id: number;
  item_name: string;
  quantity_grams: number;
  expiry_date: string;
  days_remaining: number;
  priority: 'urgent' | 'high' | 'medium';
  recipe_suggestions: Array<{
    recipe_id: number;
    recipe_name: string;
    uses_quantity: number;
    match_percentage?: number;
  }>;
}

export interface RestockItem {
  item_name: string;
  category: string;
  current_quantity: number;
  recommended_quantity: number;
  priority: string;
  usage_frequency: number;
  days_until_depleted?: number;
}

export interface RestockList {
  total_items: number;
  urgent_items: RestockItem[];
  soon_items: RestockItem[];
  routine_items: RestockItem[];
  estimated_total_cost?: number;
  shopping_strategy: string[];
}

export type ViewMode = 'grid' | 'list';

export type FilterOptions = {
  category?: string;
  lowStockOnly: boolean;
  expiringSoon: boolean;
  searchQuery: string;
};
