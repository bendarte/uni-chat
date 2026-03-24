export interface Filters {
  level: string;
  cities: string[];
  language: string;
  study_pace: string;
}

export interface Recommendation {
  id?: string;
  name: string;
  university: string;
  city: string;
  level: string;
  language: string;
  study_pace?: string;
  source_url?: string;
  explanation?: string[];
}

export interface ActiveFiltersResponse {
  city?: string;
  level?: string;
  language?: string;
  study_pace?: string;
}
