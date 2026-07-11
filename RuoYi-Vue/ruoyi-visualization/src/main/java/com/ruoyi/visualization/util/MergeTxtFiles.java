package com.ruoyi.visualization.util;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/**
 * 合并指定目录下所有 txt 文件到一个文件
 * 一次性工具，直接运行 main 方法
 */
public class MergeTxtFiles {
    public static void main(String[] args) {
        // 源目录（包含所有待合并的 txt）
        String sourceDir = "D:\\BaiduNetdiskDownload\\yolo_format\\labels\\aa";
        // 输出文件路径
        String targetFile = "D:\\BaiduNetdiskDownload\\yolo_format\\labels\\merged_with_val2.txt";

        try {
            mergeTxtFiles(sourceDir, targetFile);
            System.out.println("✅ 合并完成！输出文件：" + targetFile);
        } catch (IOException e) {
            System.err.println("❌ 合并失败：" + e.getMessage());
            e.printStackTrace();
        }
    }

    public static void mergeTxtFiles(String sourceDir, String targetFilePath) throws IOException {
        Path dir = Paths.get(sourceDir);
        if (!Files.isDirectory(dir)) {
            throw new IllegalArgumentException("源路径不是目录：" + sourceDir);
        }

        List<Path> txtFiles;
        try (Stream<Path> stream = Files.list(dir)) {
            txtFiles = stream
                    .filter(Files::isRegularFile)
                    .filter(p -> p.toString().toLowerCase().endsWith(".txt"))
                    .sorted(Path::compareTo)
                    .collect(Collectors.toList());
        }

        if (txtFiles.isEmpty()) {
            Files.createFile(Paths.get(targetFilePath));
            System.out.println("⚠️ 未找到任何 .txt 文件，已创建空目标文件。");
            return;
        }

        try (BufferedWriter writer = Files.newBufferedWriter(Paths.get(targetFilePath), StandardCharsets.UTF_8)) {
            for (Path file : txtFiles) {
                String fileName = file.getFileName().toString();
                String id = extractId(fileName);
                if (id == null) {
                    System.out.println("⚠️ 文件 " + fileName + " 不含下划线，跳过。");
                    continue;
                }

                try (BufferedReader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        // 核心修改：在行首加 '(' ，行尾加 ')'
                        writer.write("(" + id + " " + line + ")");
                        writer.newLine();
                    }
                }
            }
        }
    }

    private static String extractId(String fileName) {
        int underscoreIndex = fileName.indexOf('_');
        if (underscoreIndex == -1) {
            return null;
        }
        String afterUnderscore = fileName.substring(underscoreIndex + 1);
        int dotIndex = afterUnderscore.lastIndexOf('.');
        if (dotIndex != -1) {
            afterUnderscore = afterUnderscore.substring(0, dotIndex);
        }
        return afterUnderscore;
    }
}