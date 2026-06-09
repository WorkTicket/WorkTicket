export interface BlogPost {
  slug: string;
  title: string;
  description: string;
  date: string;
  author: string;
  readingTime: string;
}

export const blogPosts: BlogPost[] = [
  {
    slug: "getting-started-with-workticket",
    title: "Getting Started with WorkTicket",
    description: "How skilled trades businesses streamline job management from day one.",
    date: "2026-05-15",
    author: "WorkTicket Team",
    readingTime: "5 min read",
  },
  {
    slug: "estimate-approval-workflow",
    title: "Building a Faster Estimate Approval Workflow",
    description: "Reduce back-and-forth with customers and close more jobs.",
    date: "2026-04-22",
    author: "WorkTicket Team",
    readingTime: "4 min read",
  },
  {
    slug: "field-technician-mobile-tips",
    title: "5 Tips for Field Technicians Using Mobile Job Apps",
    description: "Practical advice for capturing photos, notes, and status updates on site.",
    date: "2026-03-10",
    author: "WorkTicket Team",
    readingTime: "6 min read",
  },
];

export function getPost(slug: string): BlogPost | undefined {
  return blogPosts.find((p) => p.slug === slug);
}
