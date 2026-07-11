package com.ruoyi.visualization.controller;

import com.alibaba.fastjson2.JSONArray;
import com.ruoyi.common.annotation.Anonymous;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.visualization.domain.TrainingTask;
import com.ruoyi.visualization.service.TrainingTaskService;
import jakarta.servlet.http.HttpServletResponse;
import org.apache.commons.lang3.StringUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 训练任务管理 Controller
 */
@RestController
@RequestMapping("/visiualization/training")
public class TrainingTaskController {

    private final Logger logger = LoggerFactory.getLogger(TrainingTaskController.class);

    @Autowired
    private TrainingTaskService trainingTaskService;

    /**
     * 查询所有训练任务
     */
    @GetMapping("/list")
    @Anonymous
    public AjaxResult list() {
        logger.info("查询训练任务列表开始");
        List<TrainingTask> list = trainingTaskService.selectTrainingTaskList();
        logger.info("查询训练任务列表结束，共 {} 条", list.size());
        return AjaxResult.success(list);
    }

    /**
     * 根据ID查询训练任务详情
     */
    @GetMapping("/detail")
    @Anonymous
    public AjaxResult detail(@RequestParam("id") String id) {
        logger.info("查询训练任务详情开始，id：{}", id);
        TrainingTask task = trainingTaskService.selectTrainingTaskById(id);
        if (task == null) {
            return AjaxResult.error("任务不存在");
        }
        return AjaxResult.success(task);
    }

    /**
     * 同步训练任务ID（从 epoch 结果表同步）
     */
    @PostMapping("/sync")
    @Anonymous
    public AjaxResult sync() {
        logger.info("同步训练任务ID开始");
        trainingTaskService.syncTaskIds();
        logger.info("同步训练任务ID结束");
        return AjaxResult.success("同步成功");
    }

    /**
     * 按任务ID查询 epoch 结果（用于图表展示）
     */
    @GetMapping("/epochResults")
    @Anonymous
    public AjaxResult epochResults(@RequestParam("id") String id) {
        logger.info("查询任务epoch结果开始，id：{}", id);
        JSONArray jsonArray = trainingTaskService.selectEpochResultsByTaskId(id);
        logger.info("查询任务epoch结果结束，共 {} 条", jsonArray.size());
        return AjaxResult.success(jsonArray);
    }

    /**
     * 下载模型文件 (best.pt / last.pt)
     */
    @GetMapping("/download")
    @Anonymous
    public void download(@RequestParam("id") String id,
                         @RequestParam("type") String type,
                         HttpServletResponse response) {
        logger.info("下载模型文件开始，id：{}，type：{}", id, type);

        TrainingTask task = trainingTaskService.selectTrainingTaskById(id);
        if (task == null) {
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            return;
        }

        String filePath = "best".equals(type) ? task.getBestPtPath() : task.getLastPtPath();
        if (StringUtils.isEmpty(filePath)) {
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            return;
        }

        File file = new File(filePath);
        if (!file.exists()) {
            logger.warn("模型文件不存在：{}", filePath);
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            return;
        }

        try (FileInputStream fis = new FileInputStream(file);
             OutputStream out = response.getOutputStream()) {

            response.setContentType("application/octet-stream");
            response.setHeader("Content-Disposition",
                    "attachment;filename=" + URLEncoder.encode(file.getName(), StandardCharsets.UTF_8));
            response.setContentLengthLong(file.length());

            byte[] buffer = new byte[8192];
            int len;
            while ((len = fis.read(buffer)) != -1) {
                out.write(buffer, 0, len);
            }
            out.flush();
        } catch (Exception e) {
            logger.error("下载模型文件异常", e);
        }
    }
}
