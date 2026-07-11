package com.ruoyi.visualization.domain;

import com.fasterxml.jackson.annotation.JsonFormat;
import java.util.Date;

/**
 * 模型注册实体
 */
public class ModelRegistry {

    private Long id;

    /** 模型名称 (如 Det-Fly 基准模型 V1.0) */
    private String modelName;

    /** 模型版本 */
    private String modelVersion;

    /** 模型类型 (如 YOLOv8s, YOLOv8n) */
    private String modelType;

    /** 模型文件路径 */
    private String sourcePath;

    /** 关联训练任务ID */
    private String trainingTaskId;

    /** mAP50 指标 */
    private Double metricsMap;

    /** 推理速度 (ms) */
    private Double metricsSpeed;

    /** 状态: in_use=使用中, archived=归档 */
    private String status;

    /** 备注 */
    private String remark;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getModelName() { return modelName; }
    public void setModelName(String modelName) { this.modelName = modelName; }

    public String getModelVersion() { return modelVersion; }
    public void setModelVersion(String modelVersion) { this.modelVersion = modelVersion; }

    public String getModelType() { return modelType; }
    public void setModelType(String modelType) { this.modelType = modelType; }

    public String getSourcePath() { return sourcePath; }
    public void setSourcePath(String sourcePath) { this.sourcePath = sourcePath; }

    public String getTrainingTaskId() { return trainingTaskId; }
    public void setTrainingTaskId(String trainingTaskId) { this.trainingTaskId = trainingTaskId; }

    public Double getMetricsMap() { return metricsMap; }
    public void setMetricsMap(Double metricsMap) { this.metricsMap = metricsMap; }

    public Double getMetricsSpeed() { return metricsSpeed; }
    public void setMetricsSpeed(Double metricsSpeed) { this.metricsSpeed = metricsSpeed; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getRemark() { return remark; }
    public void setRemark(String remark) { this.remark = remark; }

    public Date getCreateTime() { return createTime; }
    public void setCreateTime(Date createTime) { this.createTime = createTime; }

    public Date getUpdateTime() { return updateTime; }
    public void setUpdateTime(Date updateTime) { this.updateTime = updateTime; }
}
