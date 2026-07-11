package com.ruoyi.visualization.domain;

/**
 * 批量推理任务状态 DTO
 */
public class BatchTask {

    private String taskId;
    private String status;       // PROCESSING / COMPLETED / FAILED
    private int total;
    private int completed;
    private double percent;
    private String currentFile;
    private String resultZipPath;
    private String errorMsg;
    private long createTime;

    public String getTaskId() { return taskId; }
    public void setTaskId(String taskId) { this.taskId = taskId; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public int getTotal() { return total; }
    public void setTotal(int total) { this.total = total; }

    public int getCompleted() { return completed; }
    public void setCompleted(int completed) { this.completed = completed; }

    public double getPercent() { return percent; }
    public void setPercent(double percent) { this.percent = percent; }

    public String getCurrentFile() { return currentFile; }
    public void setCurrentFile(String currentFile) { this.currentFile = currentFile; }

    public String getResultZipPath() { return resultZipPath; }
    public void setResultZipPath(String resultZipPath) { this.resultZipPath = resultZipPath; }

    public String getErrorMsg() { return errorMsg; }
    public void setErrorMsg(String errorMsg) { this.errorMsg = errorMsg; }

    public long getCreateTime() { return createTime; }
    public void setCreateTime(long createTime) { this.createTime = createTime; }
}
