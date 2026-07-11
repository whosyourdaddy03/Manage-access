package com.ruoyi.visualization.service;

import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.visualization.domain.TrainingTask;

import java.util.List;

/**
 * 训练任务 Service 接口
 */
public interface TrainingTaskService {

    /**
     * 查询所有训练任务
     */
    List<TrainingTask> selectTrainingTaskList();

    /**
     * 根据ID查询训练任务详情
     */
    TrainingTask selectTrainingTaskById(String id);

    /**
     * 同步任务ID（从 epoch 结果表）
     */
    void syncTaskIds();

    /**
     * 按任务ID查询 epoch 结果（用于图表）
     */
    JSONArray selectEpochResultsByTaskId(String id);
}
