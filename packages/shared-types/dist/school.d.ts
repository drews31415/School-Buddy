import { CrawlStatus } from "./enums";
export interface School {
    schoolId: string;
    name: string;
    address: string;
    noticeUrl: string;
    crawlStatus: CrawlStatus;
    lastCrawledAt: string;
    lastErrorAt?: string;
    lastErrorMessage?: string;
}
//# sourceMappingURL=school.d.ts.map