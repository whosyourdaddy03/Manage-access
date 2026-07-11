package com.ruoyi.visualization.service;

import com.ruoyi.visualization.domain.BatchTask;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

/**
 * 在线推理 Service 接口
 */
public interface InferenceService {

    /**
     * 单张图片推理: 上传图片, 返回带检测框的结果图片字节 + 检测信息
     */
    Map<String, Object> singleInference(MultipartFile file) throws Exception;

    /**
     * 启动批量推理任务
     */
    BatchTask startBatchInference(MultipartFile zipFile) throws Exception;

    /**
     * 查询批量任务状态
     */
    BatchTask getBatchTaskStatus(String taskId);

    /**
     * 查询所有批量任务
     */
    List<BatchTask> listBatchTasks();

    /**
     * 获取最新检测结果摘要(供首页使用)
     */
    Map<String, Object> getLatestDetectionSummary();
}
