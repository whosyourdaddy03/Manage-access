package com.ruoyi.visualization.controller;

import com.ruoyi.common.annotation.Anonymous;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.visualization.domain.BatchTask;
import com.ruoyi.visualization.service.InferenceService;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * 在线推理 Controller
 */
@RestController
@RequestMapping("/visiualization/inference")
public class InferenceController {

    private final Logger logger = LoggerFactory.getLogger(InferenceController.class);

    @Autowired
    private InferenceService inferenceService;

    /**
     * 单张图片推理: 上传图片, 返回JSON(包含base64图片+检测信息)
     */
    @PostMapping("/single")
    @Anonymous
    public AjaxResult singleInference(@RequestParam("file") MultipartFile file) {
        logger.info("单张图片推理开始: {}", file.getOriginalFilename());
        try {
            Map<String, Object> result = inferenceService.singleInference(file);
            return AjaxResult.success(result);
        } catch (Exception e) {
            logger.error("单张推理失败", e);
            return AjaxResult.error("推理失败: " + e.getMessage());
        }
    }

    /**
     * 批量推理: 上传 zip 包, 启动后台任务
     */
    @PostMapping("/batch/start")
    @Anonymous
    public AjaxResult startBatch(@RequestParam("file") MultipartFile file) {
        logger.info("批量推理开始: {}", file.getOriginalFilename());
        try {
            BatchTask task = inferenceService.startBatchInference(file);
            return AjaxResult.success(task);
        } catch (Exception e) {
            logger.error("启动批量推理失败", e);
            return AjaxResult.error("启动失败: " + e.getMessage());
        }
    }

    /**
     * 查询批量任务状态
     */
    @GetMapping("/batch/status")
    @Anonymous
    public AjaxResult batchStatus(@RequestParam("taskId") String taskId) {
        BatchTask task = inferenceService.getBatchTaskStatus(taskId);
        return task != null ? AjaxResult.success(task) : AjaxResult.error("任务不存在");
    }

    /**
     * 批量推理任务列表
     */
    @GetMapping("/batch/list")
    @Anonymous
    public AjaxResult batchList() {
        List<BatchTask> list = inferenceService.listBatchTasks();
        return AjaxResult.success(list);
    }

    /**
     * 下载批量推理结果
     */
    @GetMapping("/batch/download")
    @Anonymous
    public void downloadBatch(@RequestParam("taskId") String taskId,
                              HttpServletResponse response) {
        BatchTask task = inferenceService.getBatchTaskStatus(taskId);
        if (task == null || task.getResultZipPath() == null) {
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            return;
        }
        File file = new File(task.getResultZipPath());
        if (!file.exists()) {
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            return;
        }
        try (FileInputStream fis = new FileInputStream(file);
             OutputStream os = response.getOutputStream()) {
            response.setContentType("application/zip");
            response.setHeader("Content-Disposition",
                    "attachment;filename=" + URLEncoder.encode("inference_result.zip", StandardCharsets.UTF_8));
            response.setContentLengthLong(file.length());
            byte[] buffer = new byte[8192];
            int len;
            while ((len = fis.read(buffer)) != -1) {
                os.write(buffer, 0, len);
            }
            os.flush();
        } catch (Exception e) {
            logger.error("下载批量结果失败", e);
        }
    }

    /**
     * 最新检测摘要(供首页使用)
     */
    @GetMapping("/latest")
    @Anonymous
    public AjaxResult latestDetection() {
        return AjaxResult.success(inferenceService.getLatestDetectionSummary());
    }
}
