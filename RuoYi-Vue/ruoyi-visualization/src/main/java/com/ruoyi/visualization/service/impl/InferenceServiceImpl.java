package com.ruoyi.visualization.service.impl;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.visualization.domain.BatchTask;
import com.ruoyi.visualization.mapper.ModelRegistryMapper;
import com.ruoyi.visualization.service.InferenceService;
import org.apache.commons.lang3.StringUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

import static java.util.Base64.getEncoder;

@Service
public class InferenceServiceImpl implements InferenceService {

    private final Logger logger = LoggerFactory.getLogger(InferenceServiceImpl.class);

    private static final String TEMP_BASE = "D:\\BaiduNetdiskDownload\\inference_temp";
    private static final String PYTHON_SCRIPT_NAME = "inference.py";
    private final ExecutorService executor = Executors.newCachedThreadPool();

    // 内存存储批量任务
    private final ConcurrentHashMap<String, BatchTask> batchTaskMap = new ConcurrentHashMap<>();
    // 最新检测摘要
    private volatile Map<String, Object> latestDetectionSummary = new HashMap<>();

    @Autowired
    private ModelRegistryMapper modelRegistryMapper;

    @Override
    public Map<String, Object> singleInference(MultipartFile file) throws Exception {
        // 1. 获取使用中的模型
        String modelPath = getInUseModelPath();
        if (modelPath == null) {
            throw new RuntimeException("没有可用的模型，请先在模型管理中心注册并启用一个模型");
        }

        // 2. 提取 Python 脚本
        String scriptPath = extractScript();

        // 3. 保存上传的图片到临时目录
        String taskDir = TEMP_BASE + "\\single_" + UUID.randomUUID().toString().substring(0, 8);
        new File(taskDir).mkdirs();

        String ext = getExtension(Objects.requireNonNull(file.getOriginalFilename()));
        String inputPath = taskDir + "\\input" + ext;
        String outputPath = taskDir + "\\output" + ext;
        file.transferTo(new File(inputPath));

        // 4. 调用 Python 推理脚本
        ProcessBuilder pb = new ProcessBuilder("python", "-u", scriptPath,
                "--model", modelPath,
                "--input", inputPath,
                "--output", outputPath);
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        pb.redirectErrorStream(true);

        Process process = pb.start();
        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line);
            }
        }
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            throw new RuntimeException("Python推理脚本执行失败: " + output);
        }

        // 5. 解析 Python 输出的 JSON
        Map<String, Object> result = new HashMap<>();
        String jsonStr = output.toString().trim();
        try {
            JSONObject json = JSON.parseObject(jsonStr);
            result.put("detections", json.get("detections"));
            result.put("count", json.get("count"));
        } catch (Exception e) {
            logger.warn("解析Python输出JSON失败: {}", jsonStr);
        }

        // 6. 读取结果图片并转为base64
        File resultFile = new File(outputPath);
        if (resultFile.exists()) {
            byte[] imageBytes = Files.readAllBytes(resultFile.toPath());
            result.put("imageBase64", getEncoder().encodeToString(imageBytes));
        }

        return result;
    }

    @Override
    public BatchTask startBatchInference(MultipartFile zipFile) throws Exception {
        // 1. 获取模型
        String modelPath = getInUseModelPath();
        if (modelPath == null) {
            throw new RuntimeException("没有可用的模型，请先在模型管理中心注册并启用一个模型");
        }

        String scriptPath = extractScript();

        // 2. 创建任务目录
        String taskId = UUID.randomUUID().toString().substring(0, 8);
        String taskDir = TEMP_BASE + "\\batch_" + taskId;
        String inputDir = taskDir + "\\input";
        String outputDir = taskDir + "\\output";
        String zipOutputDir = TEMP_BASE + "\\zip";
        new File(inputDir).mkdirs();
        new File(outputDir).mkdirs();
        new File(zipOutputDir).mkdirs();

        // 3. 保存上传的 zip 并解压
        String zipPath = taskDir + "\\upload.zip";
        zipFile.transferTo(new File(zipPath));
        unzip(zipPath, inputDir);

        // 4. 创建任务记录
        BatchTask task = new BatchTask();
        task.setTaskId(taskId);
        task.setStatus("PROCESSING");
        task.setCompleted(0);
        task.setPercent(0);
        task.setCreateTime(System.currentTimeMillis());
        batchTaskMap.put(taskId, task);

        // 5. 异步执行推理
        String finalModelPath = modelPath;
        String finalScriptPath = scriptPath;
        String finalZipPath = zipOutputDir + "\\result_" + taskId + ".zip";
        executor.submit(() -> {
            try {
                runBatchInference(finalScriptPath, finalModelPath, inputDir, outputDir, taskId, finalZipPath);
            } catch (Exception e) {
                logger.error("批量推理失败", e);
                BatchTask t = batchTaskMap.get(taskId);
                if (t != null) {
                    t.setStatus("FAILED");
                    t.setErrorMsg(e.getMessage());
                }
            }
        });

        return task;
    }

    @Async
    protected void runBatchInference(String scriptPath, String modelPath,
                                     String inputDir, String outputDir,
                                     String taskId, String resultZipPath) throws Exception {
        ProcessBuilder pb = new ProcessBuilder("python", "-u", scriptPath,
                "--model", modelPath,
                "--input_dir", inputDir,
                "--output_dir", outputDir);
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        pb.redirectErrorStream(true);

        Process process = pb.start();
        StringBuilder lastOutput = new StringBuilder();

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                lastOutput.setLength(0);
                lastOutput.append(line);
                // 解析进度 JSON
                try {
                    JSONObject progress = JSON.parseObject(line);
                    if ("progress".equals(progress.getString("type"))) {
                        BatchTask t = batchTaskMap.get(taskId);
                        if (t != null) {
                            t.setCompleted(progress.getIntValue("completed"));
                            t.setTotal(progress.getIntValue("total"));
                            t.setPercent(progress.getDoubleValue("percent"));
                            t.setCurrentFile(progress.getString("current_file"));
                        }
                    }
                } catch (Exception ignored) {
                }
            }
        }
        int exitCode = process.waitFor();

        BatchTask task = batchTaskMap.get(taskId);
        if (exitCode != 0) {
            if (task != null) {
                task.setStatus("FAILED");
                task.setErrorMsg(lastOutput.toString());
            }
            return;
        }

        // 打包结果 zip
        zipDirectory(outputDir, resultZipPath);

        // 统计检测总数
        int totalDetections = 0;
        File[] resultFiles = new File(outputDir).listFiles();
        if (resultFiles != null) {
            totalDetections = resultFiles.length;
        }

        if (task != null) {
            task.setStatus("COMPLETED");
            task.setPercent(100);
            task.setCompleted(task.getTotal());
            task.setResultZipPath(resultZipPath);
        }

        // 更新最新检测摘要
        Map<String, Object> summary = new HashMap<>();
        summary.put("taskId", taskId);
        summary.put("time", new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()));
        summary.put("totalImages", task != null ? task.getTotal() : 0);
        summary.put("totalDetections", totalDetections);
        summary.put("resultZipPath", resultZipPath);
        latestDetectionSummary = summary;
    }

    @Override
    public BatchTask getBatchTaskStatus(String taskId) {
        return batchTaskMap.get(taskId);
    }

    @Override
    public List<BatchTask> listBatchTasks() {
        List<BatchTask> list = new ArrayList<>(batchTaskMap.values());
        list.sort((a, b) -> Long.compare(b.getCreateTime(), a.getCreateTime()));
        return list;
    }

    @Override
    public Map<String, Object> getLatestDetectionSummary() {
        return latestDetectionSummary;
    }

    // ===== 工具方法 =====

    private String getInUseModelPath() {
        List<com.ruoyi.visualization.domain.ModelRegistry> models = modelRegistryMapper.selectModelList();
        for (com.ruoyi.visualization.domain.ModelRegistry m : models) {
            if ("in_use".equals(m.getStatus()) && StringUtils.isNotEmpty(m.getSourcePath())) {
                File f = new File(m.getSourcePath());
                if (f.exists()) {
                    return m.getSourcePath();
                }
            }
        }
        return null;
    }

    private synchronized String extractScript() throws IOException {
        String destPath = TEMP_BASE + "\\" + PYTHON_SCRIPT_NAME;
        File destFile = new File(destPath);

        new File(TEMP_BASE).mkdirs();
        try (InputStream is = new ClassPathResource("scripts/" + PYTHON_SCRIPT_NAME).getInputStream();
             OutputStream os = new FileOutputStream(destFile)) {
            byte[] buffer = new byte[4096];
            int len;
            while ((len = is.read(buffer)) != -1) {
                os.write(buffer, 0, len);
            }
        }
        return destPath;
    }

    private String getExtension(String filename) {
        int idx = filename.lastIndexOf('.');
        return idx >= 0 ? filename.substring(idx) : ".jpg";
    }

    private void unzip(String zipPath, String destDir) throws IOException {
        try (ZipInputStream zis = new ZipInputStream(new FileInputStream(zipPath))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;
                File outFile = new File(destDir, entry.getName());
                new File(outFile.getParent()).mkdirs();
                try (FileOutputStream fos = new FileOutputStream(outFile)) {
                    byte[] buffer = new byte[8192];
                    int len;
                    while ((len = zis.read(buffer)) != -1) {
                        fos.write(buffer, 0, len);
                    }
                }
                zis.closeEntry();
            }
        }
    }

    private void zipDirectory(String sourceDir, String zipPath) throws IOException {
        try (ZipOutputStream zos = new ZipOutputStream(new FileOutputStream(zipPath))) {
            File dir = new File(sourceDir);
            File[] files = dir.listFiles();
            if (files == null) return;
            for (File file : files) {
                if (file.isFile()) {
                    zos.putNextEntry(new ZipEntry(file.getName()));
                    Files.copy(file.toPath(), zos);
                    zos.closeEntry();
                }
            }
        }
    }
}
