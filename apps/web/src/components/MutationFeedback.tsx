type FeedbackNotice = {
  message: string;
  tone?: "success" | "error";
};

export function MutationFeedback({
  feedback,
  messages,
}: {
  feedback?: string;
  messages: Record<string, FeedbackNotice>;
}) {
  if (!feedback) return null;
  const notice = messages[feedback];
  if (!notice) return null;

  return (
    <div
      className={`mutationFeedback${notice.tone === "error" ? " mutationFeedbackError" : ""}`}
      role={notice.tone === "error" ? "alert" : "status"}
    >
      {notice.message}
    </div>
  );
}
