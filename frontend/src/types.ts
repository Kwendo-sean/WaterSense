export type Status="safe"|"watch"|"warning"|"critical"|"offline";
export interface Station{id:number;station_code:string;name:string;description:string;station_type:string;latitude:number;longitude:number;location_text:string;status:Status;last_seen_at:string;source_type:string}
export interface Reading{id:number;station_id:number;timestamp:string;ph:number|null;turbidity_ntu:number|null;temperature_c:number|null;conductivity_us_cm:number|null;tds_ppm:number|null;water_level_percent:number|null;flow_rate_l_min:number|null;battery_percent:number|null;source:string}
export interface Risk{id:number;station_id:number;timestamp:string;overall_risk_score:number;risk_level:Status;detected_factors:string[];explanation:string;recommended_action:string;confidence:number;anomaly_score:number}
export interface Alert{id:number;station_id:number;created_at:string;severity:Status;type:string;title:string;message:string;recommended_action:string;acknowledged:boolean;resolved:boolean}
export interface Summary{network_health:number;stations:number;status_counts:Record<string,number>;avg_ph:number;avg_turbidity:number;water_availability:number;active_alerts:number;readings_processed:number}
export interface Latest{station:Station;reading:Reading;risk:Risk}
export interface Activity{id:number;timestamp:string;station_id:number;station_code:string;station_name:string;risk_level:Status;risk_score:number;message:string}
