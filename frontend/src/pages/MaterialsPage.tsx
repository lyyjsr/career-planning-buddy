import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useCreateJobTarget, useCreateResumeVersion, useDeleteJobTarget, useDeleteResumeVersion, useExtractResumeDocument, useJobTargets, useResumeVersions } from "@/api/resumes";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export function MaterialsPage(): JSX.Element {
  const resumes = useResumeVersions();
  const targets = useJobTargets();
  const createResume = useCreateResumeVersion();
  const extractResume = useExtractResumeDocument();
  const createTarget = useCreateJobTarget();
  const deleteResume = useDeleteResumeVersion();
  const deleteTarget = useDeleteJobTarget();
  const [searchParams] = useSearchParams();
  const [resume, setResume] = useState<{
    label: string;
    source_text: string;
    source_type: "pasted_text" | "uploaded_file";
    source_filename?: string;
    source_media_type?: string;
  }>({ label: "我的简历", source_text: "", source_type: "pasted_text" });
  const [target, setTarget] = useState({ title: "", company: "", jd_text: "" });

  const saveResume = (event: FormEvent) => {
    event.preventDefault();
    createResume.mutate(resume, {
      onSuccess: () => setResume({ label: "我的简历", source_text: "", source_type: "pasted_text" }),
    });
  };
  const selectResumeFile = (file: File | undefined) => {
    if (!file) return;
    extractResume.mutate(file, {
      onSuccess: (result) => setResume({
        label: resume.label === "我的简历" ? file.name.replace(/\.(pdf|docx|txt)$/i, "") : resume.label,
        source_text: result.source_text,
        source_type: "uploaded_file",
        source_filename: result.filename,
        source_media_type: result.media_type,
      }),
    });
  };
  const saveTarget = (event: FormEvent) => {
    event.preventDefault();
    createTarget.mutate(target, { onSuccess: () => setTarget({ title: "", company: "", jd_text: "" }) });
  };

  return <div className="mx-auto max-w-5xl space-y-6">
    <div><h1 className="text-2xl font-semibold">求职材料</h1><p className="text-muted-foreground">保存冻结版本，历史面试不会被后续编辑改变。</p></div>
    {searchParams.get("next") === "/interviews/new" && resumes.data?.items.length && targets.data?.items.length ? <Card className="border-primary/25 bg-accent/40"><CardContent className="flex flex-wrap items-center justify-between gap-3 p-5"><p className="text-sm">材料已经齐全，可以继续刚才的面试设置。</p><Button asChild><Link to="/interviews/new">继续设置面试</Link></Button></CardContent></Card> : null}
    <div className="grid gap-6 lg:grid-cols-2">
      <Card><CardHeader><CardTitle>简历</CardTitle><CardDescription>上传 PDF、DOCX、TXT，或直接粘贴文本。保存前可以检查和修改解析结果。</CardDescription></CardHeader><CardContent>
        <form className="space-y-3" onSubmit={saveResume}>
          <Input aria-label="简历名称" value={resume.label} onChange={(e) => setResume({ ...resume, label: e.target.value })} required />
          <div className="rounded-xl border border-dashed p-4">
            <label className="block text-sm font-medium" htmlFor="resume-file">上传简历文件</label>
            <p className="mt-1 text-xs text-muted-foreground">支持 PDF、DOCX、TXT，最大 5 MiB；暂不支持扫描版或加密 PDF。</p>
            <Input id="resume-file" aria-label="上传简历文件" className="mt-3" type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" disabled={extractResume.isPending} onChange={(e) => selectResumeFile(e.target.files?.[0])} />
            {extractResume.isPending && <p role="status" className="mt-2 text-sm text-muted-foreground">正在解析简历…</p>}
            {extractResume.isError && <p className="mt-2 text-sm text-destructive">{resumeExtractError(extractResume.error)}</p>}
            {resume.source_type === "uploaded_file" && resume.source_filename && <p className="mt-2 text-sm text-emerald-700">已解析 {resume.source_filename}，请检查下方文本后保存。</p>}
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium" htmlFor="resume-text">简历文本与解析预览</label>
            <Textarea id="resume-text" aria-label="简历文本" className="min-h-52" placeholder="也可以直接粘贴简历文本" value={resume.source_text} onChange={(e) => setResume({ ...resume, source_text: e.target.value })} minLength={20} required />
          </div>
          {createResume.isError && <p className="text-sm text-destructive">简历保存失败，请检查内容后重试。</p>}
          <Button disabled={createResume.isPending || resume.label.trim().length === 0 || resume.source_text.trim().length < 20}>{createResume.isPending ? "保存中…" : "保存简历版本"}</Button>
        </form>
        {resumes.isLoading && <p role="status" className="mt-4 text-sm text-muted-foreground">正在加载简历版本…</p>}
        {resumes.isError && <p className="mt-4 text-sm text-destructive">简历列表加载失败，请刷新重试。</p>}
        {!resumes.isLoading && !resumes.isError && resumes.data?.items.length === 0 && <p className="mt-4 text-sm text-muted-foreground">还没有简历版本，请先保存上方文本。</p>}
        <div className="mt-5 space-y-2">{resumes.data?.items.map((item) => <div className="rounded-xl border p-3" key={item.resume_version_id}><div className="flex items-center justify-between gap-3"><strong>{item.label}</strong><Button type="button" size="sm" variant="ghost" disabled={deleteResume.isPending} onClick={() => window.confirm("从材料列表中移除这个简历版本？历史面试仍会保留当时的冻结内容。") && deleteResume.mutate(item.resume_version_id)}>移除</Button></div><p className="line-clamp-2 text-sm text-muted-foreground">{item.source_text}</p></div>)}</div>
      </CardContent></Card>
      <Card><CardHeader><CardTitle>目标 JD</CardTitle><CardDescription>一个 JobTarget 对应一份冻结岗位描述。</CardDescription></CardHeader><CardContent>
        <form className="space-y-3" onSubmit={saveTarget}>
          <Input aria-label="岗位名称" placeholder="岗位名称" value={target.title} onChange={(e) => setTarget({ ...target, title: e.target.value })} required />
          <Input aria-label="公司" placeholder="公司（可选）" value={target.company} onChange={(e) => setTarget({ ...target, company: e.target.value })} />
          <Textarea aria-label="JD 文本" className="min-h-44" value={target.jd_text} onChange={(e) => setTarget({ ...target, jd_text: e.target.value })} minLength={20} required />
          {createTarget.isError && <p className="text-sm text-destructive">目标岗位保存失败，请检查内容后重试。</p>}
          <Button disabled={createTarget.isPending || target.title.trim().length === 0 || target.jd_text.trim().length < 20}>{createTarget.isPending ? "保存中…" : "保存目标岗位"}</Button>
        </form>
        {targets.isLoading && <p role="status" className="mt-4 text-sm text-muted-foreground">正在加载目标岗位…</p>}
        {targets.isError && <p className="mt-4 text-sm text-destructive">目标岗位列表加载失败，请刷新重试。</p>}
        {!targets.isLoading && !targets.isError && targets.data?.items.length === 0 && <p className="mt-4 text-sm text-muted-foreground">还没有目标岗位，请先保存上方 JD。</p>}
        <div className="mt-5 space-y-2">{targets.data?.items.map((item) => <div className="rounded-xl border p-3" key={item.job_target_id}><div className="flex items-center justify-between gap-3"><strong>{item.title}{item.company ? ` · ${item.company}` : ""}</strong><Button type="button" size="sm" variant="ghost" disabled={deleteTarget.isPending} onClick={() => window.confirm("从材料列表中移除这个目标岗位？历史面试仍会保留当时的冻结内容。") && deleteTarget.mutate(item.job_target_id)}>移除</Button></div><p className="line-clamp-2 text-sm text-muted-foreground">{item.jd_text}</p></div>)}</div>
      </CardContent></Card>
    </div>
  </div>;
}

function resumeExtractError(error: Error): string {
  if (error instanceof ApiError) {
    if (error.code === "RESUME_FILE_TEXT_EMPTY") return "没有提取到可用文本；扫描版 PDF 暂不支持，请改用可复制文本的文件。";
    if (error.code === "RESUME_FILE_SIZE_INVALID") return "文件不能为空且不能超过 5 MiB。";
    if (error.code === "RESUME_FILE_FORMAT_UNSUPPORTED") return "只支持 PDF、DOCX、TXT 文件，请检查文件格式。";
  }
  return "简历解析失败，请检查文件后重试，或直接粘贴文本。";
}
