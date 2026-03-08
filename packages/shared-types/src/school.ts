import { CrawlStatus } from "./enums";

export interface School {
  schoolId: string;
  name: string;
  address: string;
  noticeUrl: string;
  crawlStatus: CrawlStatus;
  lastCrawledAt: string; // ISO 8601
  lastErrorAt?: string;  // ISO 8601
  lastErrorMessage?: string;
}
