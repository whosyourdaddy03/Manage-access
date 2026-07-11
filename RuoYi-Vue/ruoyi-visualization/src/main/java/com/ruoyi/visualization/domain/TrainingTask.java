package com.ruoyi.visualization.domain;

import com.fasterxml.jackson.annotation.JsonFormat;
import java.util.Date;

/**
 * 训练任务实体
 */
public class TrainingTask {

    /** 任务ID (如 train9, train10) */
    private String id;

    /** 训练开始时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date trainingTime;

    /** 模型版本 (如 YOLOv8s) */
    private String modelVersion;

    /** 总训练轮次 */
    private Integer epochs;

    /** 批次大小 */
    private Integer batchSize;

    /** 输入图片尺寸 */
    private Integer imageSize;

    /** best.pt 文件路径 */
    private String bestPtPath;

    /** last.pt 文件路径 */
    private String lastPtPath;

    /** 创建时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date createTime;

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public Date getTrainingTime() {
        return trainingTime;
    }

    public void setTrainingTime(Date trainingTime) {
        this.trainingTime = trainingTime;
    }

    public String getModelVersion() {
        return modelVersion;
    }

    public void setModelVersion(String modelVersion) {
        this.modelVersion = modelVersion;
    }

    public Integer getEpochs() {
        return epochs;
    }

    public void setEpochs(Integer epochs) {
        this.epochs = epochs;
    }

    public Integer getBatchSize() {
        return batchSize;
    }

    public void setBatchSize(Integer batchSize) {
        this.batchSize = batchSize;
    }

    public Integer getImageSize() {
        return imageSize;
    }

    public void setImageSize(Integer imageSize) {
        this.imageSize = imageSize;
    }

    public String getBestPtPath() {
        return bestPtPath;
    }

    public void setBestPtPath(String bestPtPath) {
        this.bestPtPath = bestPtPath;
    }

    public String getLastPtPath() {
        return lastPtPath;
    }

    public void setLastPtPath(String lastPtPath) {
        this.lastPtPath = lastPtPath;
    }

    public Date getCreateTime() {
        return createTime;
    }

    public void setCreateTime(Date createTime) {
        this.createTime = createTime;
    }
}
